import json
from typing import List, Optional

from backend.shared.clients import Neo4jClient


def _parse_sources(raw) -> list:
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return []
    return raw or []


def _build_graph(rows) -> dict:
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    edge_keys = set()

    for r in rows:
        key = (r["a_name"], r["b_name"], r["rel"])
        if key in edge_keys:
            continue
        edge_keys.add(key)

        nodes.setdefault(r["a_name"], {"id": r["a_name"], "name": r["a_name"], "label": r["a_label"], "sources": _parse_sources(r.get("a_sources"))})
        nodes.setdefault(r["b_name"], {"id": r["b_name"], "name": r["b_name"], "label": r["b_label"], "sources": _parse_sources(r.get("b_sources"))})
        edges.append({
            "source": r["a_name"],
            "target": r["b_name"],
            "type": r["rel"],
            "sources": _parse_sources(r["sources"]),
        })

    return {"nodes": list(nodes.values()), "edges": edges}


class GraphService:
    def __init__(self, client: Optional[Neo4jClient] = None):
        self._client = client or Neo4jClient()

    def search_entities(self, query: str, limit: int = 20) -> List[dict]:
        with self._client.driver.session(database=self._client.database) as session:
            rows = session.run(
                "MATCH (n) WHERE n.name CONTAINS $q "
                "RETURN labels(n)[0] AS label, n.name AS name "
                "ORDER BY n.name LIMIT $limit",
                {"q": query, "limit": limit},
            ).data()
        return [{"name": r["name"], "label": r["label"]} for r in rows]

    def get_full_graph(self) -> dict:
        with self._client.driver.session(database=self._client.database) as session:
            rows = session.run(
                "MATCH (a)-[r]->(b) "
                "RETURN labels(a)[0] AS a_label, a.name AS a_name, a.sources AS a_sources, "
                "labels(b)[0] AS b_label, b.name AS b_name, b.sources AS b_sources, "
                "type(r) AS rel, r.sources AS sources"
            ).data()
        return _build_graph(rows)

    def get_entity_graph(self, name: str) -> dict:
        with self._client.driver.session(database=self._client.database) as session:
            out_rows = session.run(
                "MATCH (a)-[r]->(b) WHERE a.name = $name "
                "RETURN labels(a)[0] AS a_label, a.name AS a_name, a.sources AS a_sources, "
                "labels(b)[0] AS b_label, b.name AS b_name, b.sources AS b_sources, "
                "type(r) AS rel, r.sources AS sources",
                {"name": name},
            ).data()

            in_rows = session.run(
                "MATCH (a)-[r]->(b) WHERE b.name = $name "
                "RETURN labels(a)[0] AS a_label, a.name AS a_name, a.sources AS a_sources, "
                "labels(b)[0] AS b_label, b.name AS b_name, b.sources AS b_sources, "
                "type(r) AS rel, r.sources AS sources",
                {"name": name},
            ).data()

            self_rows = session.run(
                "MATCH (n) WHERE n.name = $name "
                "RETURN labels(n)[0] AS label, n.name AS name, n.sources AS sources LIMIT 1",
                {"name": name},
            ).data()

        result = _build_graph(out_rows + in_rows)

        for r in self_rows:
            if r["name"] not in {n["id"] for n in result["nodes"]}:
                result["nodes"].append({"id": r["name"], "name": r["name"], "label": r["label"], "sources": _parse_sources(r.get("sources"))})

        return result


service = GraphService()
