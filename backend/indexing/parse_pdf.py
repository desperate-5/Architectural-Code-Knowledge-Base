import os
import json
import re
from html.parser import HTMLParser
from typing import List, Tuple

from llama_index.core import Document
from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter

from backend.shared.data_paths import get_parsed_dir
from backend.shared.clients import MineruClient

output_path = os.path.join(get_parsed_dir(), "chunks.json")

CHUNK_SIZE = 512
CHUNK_OVERLAP = 64


class TableToTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._rows = []
        self._current_row = []
        self._current_cell = []
        self._in_cell = False

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._current_row = []
        elif tag in ("td", "th"):
            self._in_cell = True
            self._current_cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self._in_cell = False
            self._current_row.append("".join(self._current_cell).strip())
        elif tag == "tr":
            if self._current_row:
                self._rows.append(self._current_row)
                self._current_row = []

    def handle_data(self, data):
        if self._in_cell:
            self._current_cell.append(data.strip())

    def to_text(self, table_name: str = "") -> str:
        lines = []
        if table_name:
            lines.append(f"[{table_name}]")
        for row in self._rows:
            lines.append(" | ".join(row))
        return "\n".join(lines)


def html_table_to_text(html: str, table_name: str = "") -> str:
    parser = TableToTextParser()
    parser.feed(html)
    return parser.to_text(table_name)


def extract_table_name(text_before_table: str) -> str:
    m = re.search(
        r"表\s*(\d+)[．\.](\d+)[．\.](\d+(?:-\d+)*)",
        text_before_table
    )
    if m:
        return f"表{m.group(1)}.{m.group(2)}.{m.group(3)}"
    return ""


def convert_tables_in_markdown(content: str) -> str:
    tables = re.findall(r"<table>.*?</table>", content, re.DOTALL)
    for html_table in tables:
        pos = content.find(html_table)
        name = extract_table_name(content[:pos]) if pos >= 0 else ""
        text_table = html_table_to_text(html_table, name)
        content = content.replace(html_table, text_table, 1)
    return content


def clean_text(text: str) -> str:
    text = re.sub(r"(?<=\d)\s+(?=\d)", "", text)
    text = re.sub(r"(\d)\s*,\s*(\d)", r"\1.\2", text)
    text = re.sub(r"(\d)\s+\.\s+(\d)", r"\1.\2", text)
    text = re.sub(r"(?<=\.)\s+(?=\d)", "", text)
    text = re.sub(r"(\d)\s+(?=[a-zA-Z%×])", r"\1", text)
    text = re.sub(r"([a-zA-Z])2(?=[/\s\)\,一-鿿]|$)", r"\1²", text)
    text = re.sub(r"([a-zA-Z])3(?=[/\s\)\,一-鿿]|$)", r"\1³", text)
    text = re.sub(r"([一-鿿])\s+([一-鿿])", r"\1\2", text)
    text = re.sub(r"[ \t]+", " ", text).strip()
    return text


def extract_articles(text: str) -> List[str]:
    matches = re.findall(r"(\d+)[．\.](\d+)[．\.](\d+)", text)
    return list(set(f"{a}.{b}.{c}" for a, b, c in matches))


def _is_chapter_heading(text: str) -> bool:
    return bool(re.match(r"^\d+\s+[一-鿿]", text))


def _is_section_heading(text: str) -> bool:
    return bool(re.match(r"^\d+\.\d+\s", text.replace("．", ".")))


def _extract_heading_from_node(raw_text: str) -> str:
    first_line = raw_text.split("\n", 1)[0].strip()
    if first_line.startswith("# "):
        return first_line[2:].strip()
    return ""


def build_chunks_from_markdown(
    md_text: str,
    filename: str = "document.pdf",
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
    progress_callback=None,
) -> List[dict]:
    doc = Document(text=md_text)

    md_parser = MarkdownNodeParser()
    heading_nodes = md_parser.get_nodes_from_documents([doc])

    splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    current_chapter = ""
    current_section = ""

    total_nodes = len(heading_nodes)
    chunks = []
    for idx, node in enumerate(heading_nodes):
        raw_text = node.get_content()

        heading = _extract_heading_from_node(raw_text)
        if heading:
            if _is_chapter_heading(heading):
                current_chapter = heading
                current_section = ""
            elif _is_section_heading(heading):
                current_section = heading

        body = raw_text
        if body.startswith("# "):
            idx_nl = body.find("\n")
            if idx_nl != -1:
                body = body[idx_nl + 1:]
            else:
                body = ""

        text = clean_text(body)
        if text:
            if len(text) <= chunk_size * 2:
                chunk = {
                    "text": text,
                    "metadata": {
                        "filename": filename,
                        "chapter": current_chapter,
                        "section": current_section,
                        "articles": extract_articles(text),
                    }
                }
                chunks.append(chunk)
            else:
                sub_doc = Document(text=text)
                sub_nodes = splitter.get_nodes_from_documents([sub_doc])
                for sn in sub_nodes:
                    sub_text = sn.get_content().strip()
                    if not sub_text:
                        continue
                    chunk = {
                        "text": sub_text,
                        "metadata": {
                            "filename": filename,
                            "chapter": current_chapter,
                            "section": current_section,
                            "articles": extract_articles(sub_text),
                        }
                    }
                    chunks.append(chunk)

        if progress_callback:
            progress_callback(idx + 1, total_nodes, "切分 chunk")

    return chunks


def parse_document(
    pdf_path: str,
    doc_id: str,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
    progress_callback=None,
    filename: str | None = None,
) -> int:
    filename = filename or os.path.basename(pdf_path)

    if progress_callback:
        progress_callback(0, 1, "调用 MinerU API 解析 PDF")
    content = MineruClient().parse_pdf_to_markdown(pdf_path)

    content = convert_tables_in_markdown(content)

    chunks = build_chunks_from_markdown(
        content,
        filename=filename,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        progress_callback=progress_callback,
    )

    for c in chunks:
        c["metadata"]["doc_id"] = doc_id

    parsed_dir = get_parsed_dir()
    os.makedirs(parsed_dir, exist_ok=True)

    chunks_path = os.path.join(parsed_dir, f"{doc_id}.chunks.json")
    with open(chunks_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    md_path = os.path.join(parsed_dir, f"{doc_id}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(content)

    return len(chunks)


def main(pdf_path: str):
    print("=" * 60)
    print("  PDF 解析工具")
    print("=" * 60)

    filename = os.path.basename(pdf_path)

    print("\n[Step 1] 调用 MinerU API 解析 PDF...")
    content = MineruClient().parse_pdf_to_markdown(pdf_path)
    print(f"  → Markdown 长度: {len(content)} 字符")

    print("\n[Step 2] 转换 HTML 表格为纯文本...")
    content = convert_tables_in_markdown(content)
    print(f"  → 转换完成")

    print("\n[Step 3] 使用 llama_index 按标题切分构建 chunk...")
    chunks = build_chunks_from_markdown(content, filename=filename)
    print(f"  → 共生成 {len(chunks)} 个 chunk")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    print(f"\n  → 已保存到: {output_path}")

    if chunks:
        total_len = sum(len(c["text"]) for c in chunks)
        avg_len = total_len // len(chunks)
        print(f"\n  → 总字数: {total_len}, 平均每个 chunk: {avg_len} 字")
        print(f"  → chunk_size={CHUNK_SIZE}, chunk_overlap={CHUNK_OVERLAP}")

    print("\n" + "=" * 60)
    print("  解析完成！")
    print("=" * 60)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python -m backend.indexing.parse_pdf <pdf_path>")
        sys.exit(1)
    main(sys.argv[1])
