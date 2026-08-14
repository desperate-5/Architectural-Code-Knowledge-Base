import os
import sys
import argparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def run_parse_pdf(pdf_path: str):
    print("\n" + "=" * 60)
    print("  [1/4] PDF 文档解析")
    print("=" * 60)
    from backend.indexing.parse_pdf import main as parse_main
    parse_main(pdf_path)


def run_keyword_index():
    print("\n" + "=" * 60)
    print("  [2/4] 关键词索引构建")
    print("=" * 60)
    from backend.indexing.build_keyword_index import main as keyword_main
    keyword_main()


def run_vector_index():
    print("\n" + "=" * 60)
    print("  [3/4] 向量索引构建")
    print("=" * 60)
    from backend.indexing.build_vector_index import main as vector_main
    vector_main()


def run_graph_index(write_to_neo4j: bool = False):
    print("\n" + "=" * 60)
    print("  [4/4] 知识图谱索引构建")
    print("=" * 60)
    from backend.indexing.build_graph_index import main as graph_main
    graph_main(write_to_neo4j=write_to_neo4j)


def main():
    parser = argparse.ArgumentParser(
        description="建筑规范索引构建工具 —— 统一管理多种索引构建流程"
    )
    parser.add_argument("--parse", action="store_true", help="重新解析 PDF")
    parser.add_argument("--keyword", action="store_true", help="构建关键词索引")
    parser.add_argument("--vector", action="store_true", help="构建向量索引")
    parser.add_argument("--graph", action="store_true", help="构建知识图谱索引")
    parser.add_argument("--neo4j", action="store_true", help="知识图谱结果写入 Neo4j（需配合 --graph 使用）")
    parser.add_argument("--all", action="store_true", help="构建所有索引（默认行为）")
    parser.add_argument("--pdf", help="输入 PDF 文件路径（--parse / --all 时必填）")

    args = parser.parse_args()

    has_specific_tasks = args.parse or args.keyword or args.vector or args.graph
    build_all = args.all or not has_specific_tasks

    if (args.parse or build_all) and not args.pdf:
        parser.error("--parse / --all 需要指定 --pdf <PDF 文件路径>")

    if args.parse or build_all:
        run_parse_pdf(args.pdf)

    if args.keyword or build_all:
        run_keyword_index()

    if args.vector or build_all:
        run_vector_index()

    if args.graph or build_all:
        run_graph_index(write_to_neo4j=args.neo4j)

    print("\n" + "=" * 60)
    print("  全部任务执行完毕！")
    print("=" * 60)


if __name__ == "__main__":
    main()
