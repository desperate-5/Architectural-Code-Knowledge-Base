import re
import jieba


_QUERY_NOISE = {
    "请问", "我想问", "我想", "想问", "问一下", "问下", "我想知道", "告诉我",
    "如何", "怎样", "怎么", "为啥", "为什么", "啥是", "什么是",
    "哪些", "有哪些", "吧", "吗", "呢", "啊",
    "的话", "来说", "而言",
    "帮我", "能帮我", "麻烦", "能不能", "可不可以",
    "应该", "需要", "想要",
    "的", "了", "是", "有",
    "要", "才", "多大", "想",
}

_TERM_MAP = {
    "防火的": "防火",
    "消防的": "消防",
    "结构的": "结构",
    "电气的": "电气",
    "建筑高度多少": "建筑高度",
    "高度多少": "建筑高度",
    "层高多少": "层高",
    "间距多少": "间距",
    "距离多少": "距离",
    "宽度多少": "宽度",
    "面积多少": "面积",
    "是啥": "",
    "是啥子": "",
    "是什么": "",
    "是多少": "",
    "多大才合格": "",
    "要多大": "",
    "合格": "",
    "的规定": "",
    "的规范": "",
}


def clean_query(query: str) -> str:
    if not query or not query.strip():
        return ""

    text = query.strip()

    text = re.sub(r"[^一-鿿\w\s]", " ", text)

    tokens = jieba.lcut(text)
    text = "".join(t for t in tokens if t not in _QUERY_NOISE and t.strip())

    for old, new in _TERM_MAP.items():
        text = text.replace(old, new)

    text = re.sub(r"\s+", "", text)

    return text
