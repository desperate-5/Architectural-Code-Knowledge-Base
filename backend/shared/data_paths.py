import os


def get_project_root() -> str:
    root = os.getenv("RAG_PROJECT_ROOT")
    if root:
        return os.path.abspath(root)
    current = os.path.dirname(os.path.abspath(__file__))
    for _ in range(10):
        if os.path.exists(os.path.join(current, ".env")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return os.getcwd()


def get_data_dir() -> str:
    return os.getenv("RAG_DATA_DIR", os.path.join(get_project_root(), "data"))


def get_chroma_dir() -> str:
    return os.path.join(get_data_dir(), "chroma_db")


def get_index_dir() -> str:
    return os.path.join(get_data_dir(), "index")


def get_parsed_dir() -> str:
    return os.path.join(get_data_dir(), "parsed")


def get_documents_dir() -> str:
    return os.path.join(get_data_dir(), "documents")


def get_history_db() -> str:
    return os.path.join(get_data_dir(), "history.db")
