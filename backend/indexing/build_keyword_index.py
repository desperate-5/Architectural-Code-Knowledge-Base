import os
import json
import shutil
from collections import defaultdict

import jieba
from whoosh.index import create_in
from whoosh.fields import Schema, TEXT, STORED
from whoosh.analysis import Tokenizer, Token, LowercaseFilter

from backend.shared.data_paths import get_parsed_dir, get_index_dir

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHUNKS_PATH = os.path.join(get_parsed_dir(), "chunks.json")
DICT_PATH = os.path.join(BASE_DIR, "规范词典.txt")
INDEX_DIR = get_index_dir()


def parse_domain_dict(dict_path: str) -> tuple[dict[str, list[str]], set[str]]:
    categories = {}
    all_terms = set()

    with open(dict_path, "r", encoding="utf-8") as f:
        content = f.read()

    ns = {}
    exec(content, ns)
    raw = ns.get("building_code_keywords", {})

    for cat, terms in raw.items():
        cleaned = []
        for t in terms:
            t = t.strip()
            if t:
                cleaned.append(t)
                all_terms.add(t)
        if cleaned:
            categories[cat] = cleaned

    return categories, all_terms


def register_domain_terms(terms: set[str]):
    for term in terms:
        jieba.add_word(term, freq=100000, tag="n")


def load_chunks(json_path: str) -> list[dict]:
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


class ChineseTokenizer(Tokenizer):
    def __call__(self, text, **kwargs):
        tokens = jieba.lcut(text)
        for t in tokens:
            if t.strip():
                yield Token(original=t, text=t, pos=0, startpos=0, endpos=0, boost=1.0)


def ChineseAnalyzer():
    return ChineseTokenizer() | LowercaseFilter()


def build_whoosh_index(chunks: list[dict], index_dir: str, progress_callback=None):
    analyzer = ChineseAnalyzer()
    schema = Schema(
        text=TEXT(analyzer=analyzer, stored=True),
        filename=STORED,
        chapter=STORED,
        section=STORED,
        articles=STORED,
    )

    if os.path.exists(index_dir):
        shutil.rmtree(index_dir)
    os.makedirs(index_dir, exist_ok=True)

    ix = create_in(index_dir, schema)
    writer = ix.writer()

    total = len(chunks)
    for i, c in enumerate(chunks):
        text = c.get("text", "").strip()
        if text:
            meta = c.get("metadata", {})
            writer.add_document(
                text=text,
                filename=meta.get("filename", ""),
                chapter=meta.get("chapter", ""),
                section=meta.get("section", ""),
                articles=json.dumps(meta.get("articles", []), ensure_ascii=False),
            )
        if progress_callback:
            progress_callback(i + 1, total, "写入 Whoosh 索引")

    writer.commit()
    return ix


def main(progress_callback=None):
    print("=" * 60)
    print("  关键词索引构建工具 (Whoosh)")
    print("=" * 60)

    print("\n[Step 1] 加载 chunks.json...")
    chunks = load_chunks(CHUNKS_PATH)
    print(f"  → 共加载 {len(chunks)} 个 chunk")

    print("\n[Step 2] 解析领域词典...")
    domain_categories, domain_terms = parse_domain_dict(DICT_PATH)
    print(f"  → 共 {len(domain_categories)} 个分类, {len(domain_terms)} 个领域术语")

    print("\n[Step 3] 注册领域词典到 jieba（Whoosh 中文分词依赖 jieba）...")
    register_domain_terms(domain_terms)
    print(f"  → 已注册 {len(domain_terms)} 个领域术语")

    print("\n[Step 4] 构建 Whoosh 索引...")
    build_whoosh_index(chunks, INDEX_DIR, progress_callback=progress_callback)
    print(f"  → Whoosh 索引构建完成")
    print(f"  → 索引目录: {INDEX_DIR}")

    print("\n[Step 5] 统计领域术语命中分布...")
    cat_stats = defaultdict(int)
    for c in chunks:
        text = c.get("text", "").strip()
        if not text:
            continue
        tokens = set(jieba.lcut(text))
        for term in domain_terms:
            if term in tokens:
                cat_stats[term] += 1
    category_hits = defaultdict(int)
    for cat, terms in domain_categories.items():
        hits = sum(1 for t in terms if cat_stats[t] > 0)
        category_hits[cat] = hits
    print("  → 领域术语命中分布:")
    for cat, hits in sorted(category_hits.items(), key=lambda x: -x[1]):
        total = len(domain_categories[cat])
        print(f"      {cat}: {hits}/{total} 个术语命中")

    print("\n[Step 6] 保存领域词典元数据...")
    meta_path = os.path.join(INDEX_DIR, "domain_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({
            "domain_categories": domain_categories,
            "domain_terms": list(domain_terms),
        }, f, ensure_ascii=False, indent=2)
    print(f"  [OK] {meta_path}")

    print("\n" + "=" * 60)
    print("  构建完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
