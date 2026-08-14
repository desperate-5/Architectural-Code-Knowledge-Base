import os
import json
from typing import List, Optional

from backend.shared.clients import EmbedClient, ChromaClient
from backend.shared.data_paths import get_parsed_dir

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_chunks_from_json(json_path: str) -> List[dict]:
    with open(json_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    return chunks


def build_index(
    chunks: List[dict],
    embed: Optional[EmbedClient] = None,
    chroma: Optional[ChromaClient] = None,
    batch_size: int = 10,
    progress_callback=None,
):
    embed = embed or EmbedClient()
    chroma = chroma or ChromaClient()

    print("  → 清空旧向量数据...")
    chroma.reset()
    collection = chroma.collection

    total = 0
    total_chunks = len(chunks)
    batch_ids, batch_texts, batch_metadatas = [], [], []

    def flush():
        nonlocal total
        embeddings = embed.get_embeddings(batch_texts)
        collection.add(
            ids=batch_ids,
            embeddings=embeddings,
            documents=batch_texts,
            metadatas=batch_metadatas,
        )
        total += len(batch_ids)
        print(f"  → 已写入 {total} 条...")

    for i, chunk in enumerate(chunks):
        text = chunk.get("text", "").strip()
        if text:
            meta = chunk.get("metadata", {})
            batch_ids.append(f"chunk_{i}")
            batch_texts.append(text)
            batch_metadatas.append({
                "filename": meta.get("filename", ""),
                "chapter": meta.get("chapter", ""),
                "section": meta.get("section", ""),
                "articles": ",".join(meta.get("articles", [])) if meta.get("articles") else "",
            })

        if len(batch_ids) >= batch_size:
            flush()
            batch_ids, batch_texts, batch_metadatas = [], [], []

        if progress_callback:
            progress_callback(i + 1, total_chunks, "embedding 并写入 ChromaDB")

    if batch_ids:
        flush()

    return total


def main(progress_callback=None):
    json_path = os.path.join(get_parsed_dir(), "chunks.json")

    print("=" * 60)
    print("  向量索引构建工具")
    print("=" * 60)

    if not os.path.exists(json_path):
        print(f"\n[ERROR] 未找到分块数据文件: {json_path}")
        print(f"        请先执行解析步骤生成 chunks.json")
        return

    print("\n[Step 1] 加载 chunks.json 分块数据...")
    chunks = load_chunks_from_json(json_path)
    print(f"  → 读取到 {len(chunks)} 个 chunk")

    print("\n[Step 2] embedding 并写入 ChromaDB...")
    total = build_index(chunks, progress_callback=progress_callback)
    chroma = ChromaClient()
    print(f"  → 共写入 {total} 条，向量库保存在 {chroma.persist_dir}")

    print("\n" + "=" * 60)
    print("  向量索引构建完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
