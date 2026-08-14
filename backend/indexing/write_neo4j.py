import os
import json
import argparse
from typing import Optional

from backend.shared.clients import Neo4jClient
from backend.shared.data_paths import get_parsed_dir

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NODES_PATH = os.path.join(get_parsed_dir(), "nodes.json")
RELATIONS_PATH = os.path.join(get_parsed_dir(), "relations.json")


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_label_map(nodes):
    return {n["name"]: n["label"] for n in nodes}


def deduplicate_sources(sources):
    seen = set()
    unique = []
    for s in sources:
        key = (s.get("filename", ""), s.get("chapter", ""),
               s.get("section", ""), s.get("clause", ""))
        if key not in seen:
            seen.add(key)
            unique.append(s)
    return unique


def create_indexes(client: Neo4jClient, labels):
    with client.driver.session(database=client.database) as session:
        for label in set(labels):
            try:
                session.run(
                    f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:`{label}`) REQUIRE n.name IS UNIQUE"
                )
            except Exception as e:
                print(f"  [警告] 约束创建失败 ({label}): {e}")


def write_nodes(client: Neo4jClient, nodes, batch_size=100):
    total = len(nodes)
    with client.driver.session(database=client.database) as session:
        for i in range(0, total, batch_size):
            batch = nodes[i:i + batch_size]
            for node in batch:
                session.run(
                    f"MERGE (n:`{node['label']}` {{name: $name}}) "
                    "SET n.sources = $sources",
                    name=node["name"],
                    sources=json.dumps(node["sources"], ensure_ascii=False),
                )
            print(f"\r  节点写入 [{min(i + batch_size, total)}/{total}]", end="")
    print()


def write_relations(client: Neo4jClient, relations, label_map, batch_size=100):
    total = len(relations)
    skipped = 0
    with client.driver.session(database=client.database) as session:
        for i in range(0, total, batch_size):
            batch = relations[i:i + batch_size]
            for rel in batch:
                from_label = label_map.get(rel["from"])
                to_label = label_map.get(rel["to"])
                if not from_label or not to_label:
                    skipped += 1
                    continue
                sources_json = json.dumps(
                    deduplicate_sources(rel["sources"]), ensure_ascii=False
                )
                session.run(
                    f"MATCH (a:`{from_label}` {{name: $from_name}}) "
                    f"MATCH (b:`{to_label}` {{name: $to_name}}) "
                    f"MERGE (a)-[r:`{rel['rel']}`]->(b) "
                    "SET r.sources = $sources",
                    from_name=rel["from"],
                    to_name=rel["to"],
                    sources=sources_json,
                )
            print(f"\r  关系写入 [{min(i + batch_size, total)}/{total}]", end="")
    print()
    if skipped:
        print(f"  [注意] {skipped} 条关系因节点不存在被跳过")


def clear_all(client: Neo4jClient):
    with client.driver.session(database=client.database) as session:
        session.run("MATCH (n) DETACH DELETE n")
    print("  已清空现有数据")


def write_to_neo4j(client: Optional[Neo4jClient] = None, replace: bool = False):
    nodes = load_json(NODES_PATH)
    relations = load_json(RELATIONS_PATH)

    client = client or Neo4jClient()
    client.driver.verify_connectivity()

    if replace:
        clear_all(client)

    labels = [n["label"] for n in nodes]
    create_indexes(client, labels)
    write_nodes(client, nodes)

    label_map = build_label_map(nodes)
    write_relations(client, relations, label_map)

    return len(nodes), len(relations)


def main(client: Optional[Neo4jClient] = None):
    parser = argparse.ArgumentParser(description="知识图谱 Neo4j 导入工具")
    parser.add_argument("--replace", action="store_true", help="清空旧数据后重新导入")
    args = parser.parse_args()

    print("=" * 60)
    print("  知识图谱 Neo4j 导入工具")
    print("=" * 60)

    node_count, rel_count = write_to_neo4j(client=client, replace=args.replace)

    print(f"\n{'=' * 60}")
    print(f"  导入完成！")
    print(f"  节点: {node_count} 个")
    print(f"  关系: {rel_count} 条")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
