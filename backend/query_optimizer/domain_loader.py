import os
import json

from backend.shared.data_paths import get_index_dir


class DomainLoader:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self):
        meta_path = os.path.join(get_index_dir(), "domain_meta.json")
        if not os.path.exists(meta_path):
            self.terms: set[str] = set()
            self.categories: dict[str, list[str]] = {}
            return

        with open(meta_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.terms: set[str] = set(data.get("domain_terms", []))
        self.categories: dict[str, list[str]] = data.get("domain_categories", {})
