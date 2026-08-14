import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.shared.clients import Neo4jClient
from backend.shared.data_paths import get_parsed_dir
from backend.indexing.build_graph_index import main as build_graph_main
from backend.indexing.write_neo4j import (
    clear_all,
    load_json,
    build_label_map,
    create_indexes,
    write_nodes,
    write_relations,
)

NODES_PATH = os.path.join(get_parsed_dir(), "nodes.json")
RELATIONS_PATH = os.path.join(get_parsed_dir(), "relations.json")


def _count_graph(client):
    with client.driver.session(database=client.database) as session:
        nodes = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        rels = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
    return nodes, rels


def main():
    print("=" * 60)
    print("  知识图谱构建测试")
    print("=" * 60)

    print("\n[1/5] 连接 Neo4j...")
    client = Neo4jClient()
    client.driver.verify_connectivity()
    print("  连接成功")

    before_nodes, before_rels = _count_graph(client)
    print(f"  清空前图库：{before_nodes} 节点 / {before_rels} 关系")

    print("\n[2/5] 清空图数据库...")
    clear_all(client)
    after_clear_nodes, after_clear_rels = _count_graph(client)
    print(f"  清空后图库：{after_clear_nodes} 节点 / {after_clear_rels} 关系")

    print("\n[3/5] 运行新版知识图谱构建逻辑...")
    build_graph_main(write_to_neo4j=False)

    print("\n[4/5] 加载新生成的图数据...")
    nodes = load_json(NODES_PATH)
    relations = load_json(RELATIONS_PATH)
    print(f"  节点：{len(nodes)} 个")
    print(f"  关系：{len(relations)} 条")

    print("\n[5/5] 写入 Neo4j...")
    labels = [n["label"] for n in nodes]
    create_indexes(client, labels)
    write_nodes(client, nodes)
    label_map = build_label_map(nodes)
    write_relations(client, relations, label_map)

    final_nodes, final_rels = _count_graph(client)
    print(f"\n{'=' * 60}")
    print(f"  测试完成！")
    print(f"  写入后图库：{final_nodes} 节点 / {final_rels} 关系")
    print(f"{'=' * 60}")

    client.driver.close()


if __name__ == "__main__":
    main()