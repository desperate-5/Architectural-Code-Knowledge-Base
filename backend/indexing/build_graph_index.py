import os
import json
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend.shared.clients import LLMClient
from backend.shared.data_paths import get_parsed_dir

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHUNKS_PATH = os.path.join(get_parsed_dir(), "chunks.json")
OUTPUT_DIR = get_parsed_dir()
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "triples_output.json")

os.makedirs(OUTPUT_DIR, exist_ok=True)

FEW_SHOT_EXAMPLES = [
    {
        "text": "楼梯踏步的宽度不应小于0.26m。",
        "output": {
            "triples": [
                {"subject": "楼梯踏步宽度", "predicate": "不小于", "object": "0.26m"},
            ],
        },
    },
    {
        "text": "走廊和公共部位通道的净宽不应小于1.20m。",
        "output": {
            "triples": [
                {"subject": "走廊净宽", "predicate": "不小于", "object": "1.20m"},
                {"subject": "公共部位通道净宽", "predicate": "不小于", "object": "1.20m"},
            ],
        },
    },
    {
        "text": "外廊、内天井及上人屋面等临空处应设置栏杆。",
        "output": {
            "triples": [
                {"subject": "外廊", "predicate": "必须设置", "object": "栏杆"},
                {"subject": "内天井", "predicate": "必须设置", "object": "栏杆"},
                {"subject": "上人屋面", "predicate": "必须设置", "object": "栏杆"},
            ],
        },
    },
    {
        "text": "垂直杆件间净距不应大于0.11m。",
        "output": {
            "triples": [
                {"subject": "垂直杆件间净距", "predicate": "不大于", "object": "0.11m"},
            ],
        },
    },
]

FEW_SHOT_BLOCK = "\n\n".join(
    f"## 示例 {i+1}\n文本：{ex['text']}\n输出：\n```json\n{json.dumps(ex['output'], ensure_ascii=False, indent=2)}\n```"
    for i, ex in enumerate(FEW_SHOT_EXAMPLES)
)

SYSTEM_PROMPT = f"""你是建筑规范领域的知识抽取专家。你的任务是从建筑规范文本中抽取**具体的数值约束**和**构件—安全设施关系**，输出结构化 JSON。

## 实体类型（只能使用以下 3 类）
- 建筑部位：具体构件及其属性，属性要并入实体名，如"楼梯踏步宽度"、"走廊净宽"、"栏杆净高"、"外廊"等。
- 安全设施：栏杆、扶手、防护设施、安全出口等安全相关的具体设施。
- 规范数值：具体数字要求，如"0.26m"、"1.05m"、"2.00m"。

## 关系类型（只能使用以下 6 种）
- 不小于 / 不大于 / 大于 / 小于 / 等于：连接 建筑部位 和 规范数值，表示数值约束。
  例如：楼梯踏步宽度 不小于 0.26m。
- 必须设置：连接 建筑部位 和 安全设施，表示该部位必须设置某设施。
  例如：外廊 必须设置 栏杆。

## 抽取规则（必须严格遵守）
1. 只抽取**具体数值约束**和**构件—设施关系**。
2. **严禁**抽取类型级关系，例如"住宅 应满足 防火安全要求"、"地基基础 结构要求 承载力"、"既有住宅 应满足 节能" 这类一律不抽。
3. 实体名要完整且干净：
   - 属性并入实体名（写"楼梯踏步宽度"，不要拆成"楼梯踏步"+"最小宽度"）。
   - 不要带代词前缀（其/该/此/本）。
   - 不要把关系词或数值混进实体名。
   - 不要输出孤立抽象实体（如"节能"、"防火"、"材料"、"设备"、"住宅"）。
4. 比较关系只能用"不小于/不大于/大于/小于/等于"，不要用"最小宽度/最小高度/最大间距"这类。

## Few-Shot 示例
{FEW_SHOT_BLOCK}

## 输出格式
严格输出 JSON 对象，包含以下字段：
{{
  "triples": [
    {{"subject": "主体名称", "predicate": "关系名称", "object": "客体名称"}}
  ]
}}

只输出 JSON，不要包含其他解释文字。"""


# ---------- 规范化 ----------

COMPARISON_ALIASES = {
    "不应小于": "不小于", "不应低于": "不小于", "不小于": "不小于", "不得小于": "不小于", "≥": "不小于",
    "不应大于": "不大于", "不应高于": "不大于", "不大于": "不大于", "不得大于": "不大于", "≤": "不大于",
    "应大于": "大于", "大于": "大于", ">": "大于",
    "应小于": "小于", "小于": "小于", "<": "小于",
    "应为": "等于", "等于": "等于", "=": "等于",
    "最小宽度": "不小于", "最小高度": "不小于", "最小面积": "不小于",
    "最大间距": "不大于", "最大高度": "不大于",
    "应设置": "必须设置", "应设": "必须设置", "应配备": "必须设置", "必须设置": "必须设置",
}

ALLOWED_PREDICATES = {"不小于", "不大于", "大于", "小于", "等于", "必须设置"}

LEADING_PRONOUNS = "其该此及和与或的"
FORBIDDEN_FRAGMENTS = ("本条", "本规范", "本标准", "提出", "满足", "不应", "不得")
BARE_ATTRS = {"宽度", "高度", "间距", "面积", "净高", "净宽", "净距", "坡度", "进深", "开间"}

NUMERIC_RE = re.compile(r"^\d+(\.\d+)?\s*(m|mm|cm|m²|㎡|m³|%|米|毫米|厘米|平方米)?$")

TRAILING_CMP_RE = re.compile(
    r"(不应小于|不应大于|不应低于|不应高于|不小于|不大于|不得小于|不得大于|大于|小于|等于)+$"
)


def normalize_predicate(pred):
    if not pred:
        return None
    return COMPARISON_ALIASES.get(str(pred).strip())


def normalize_value(raw):
    if raw is None:
        return None
    v = str(raw).strip().replace("O", "0").replace("o", "0")
    v = v.replace(" ", "")
    return v if NUMERIC_RE.match(v) else None


def normalize_entity_name(name):
    if not name:
        return None
    name = str(name).strip()
    while name and name[0] in LEADING_PRONOUNS:
        name = name[1:]
    name = name.lstrip("，,、。；;：: ")
    name = TRAILING_CMP_RE.sub("", name)
    name = name.rstrip("，,、。；;：: 的")
    if not name or len(name) <= 1:
        return None
    if name in BARE_ATTRS or any(f in name for f in FORBIDDEN_FRAGMENTS):
        return None
    return name


# ---------- 正则兜底 ----------

ATTRS = [
    "净宽", "宽度", "净高", "高度", "净距", "间距",
    "踏步宽度", "踏步高度", "扶手高度", "栏杆高度", "栏杆净高",
    "面积", "坡度", "进深", "开间",
]
ATTR_RE = "|".join(re.escape(a) for a in sorted(ATTRS, key=len, reverse=True))

CMP_TOKENS = [
    "不应小于", "不应低于", "不应大于", "不应高于",
    "不小于", "不大于", "不得小于", "不得大于",
    "大于", "小于", "等于", "≥", "≤", ">", "<", "=",
]
CMP_RE = "|".join(re.escape(c) for c in sorted(CMP_TOKENS, key=len, reverse=True))

NUMERICAL_PATTERN = re.compile(
    rf"([一-鿿（）\w·]+?)"
    rf"(?:的)?\s*({ATTR_RE})\s*"
    rf"({CMP_RE})\s*"
    rf"([\d]+\.?[\dOo]*)(?![\d/])\s*(m|mm|cm|m²|㎡|m³|%|米|毫米|厘米|平方米)?"
)


def extract_numerical_fallback(text):
    triples = []
    for m in NUMERICAL_PATTERN.finditer(text):
        subject = m.group(1)
        attr = m.group(2)
        cmp_raw = m.group(3)
        value = m.group(4)
        unit = m.group(5) or ""
        entity_name = subject + attr
        pred = normalize_predicate(cmp_raw)
        val = normalize_value(value + unit)
        if not pred or val is None:
            continue
        triples.append({"subject": entity_name, "predicate": pred, "object": val})
    return {"triples": triples}


# ---------- 合并与过滤 ----------

def merge_triples(llm_result, rule_result):
    merged = []
    seen = set()
    for t in (llm_result.get("triples", []) + rule_result.get("triples", [])):
        key = (t.get("subject"), t.get("predicate"), t.get("object"))
        if key not in seen:
            seen.add(key)
            merged.append(t)
    return merged


def filter_triples(raw_triples):
    kept = []
    for t in raw_triples:
        pred = normalize_predicate(t.get("predicate"))
        if pred is None or pred not in ALLOWED_PREDICATES:
            continue
        subj = normalize_entity_name(t.get("subject"))
        if not subj:
            continue
        if pred == "必须设置":
            obj = normalize_entity_name(t.get("object"))
            if not obj or NUMERIC_RE.match(obj):
                continue
            kept.append({"subject": subj, "predicate": pred, "object": obj})
        else:
            obj = normalize_value(t.get("object"))
            if obj is None:
                continue
            kept.append({"subject": subj, "predicate": pred, "object": obj})
    return kept


# ---------- 其它 ----------

def load_chunks():
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def init_client():
    llm = LLMClient()
    if not llm.client:
        raise ValueError("DEEPSEEK_API_KEY 未设置，请检查 .env 文件")
    return llm


def _parse_json_response(content):
    content = content.strip()
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
    if json_match:
        content = json_match.group(1)
    content = content.strip()
    if not content:
        raise ValueError("提取 JSON 后内容为空")
    return json.loads(content)


def extract_single(llm, text, metadata):
    user_prompt = f"""请从以下建筑规范文本中抽取实体和关系。

文本内容：
{text}

文本元数据（供参考）：
文件名：{metadata.get('filename', '')}
章节：{metadata.get('chapter', '')}
节：{metadata.get('section', '')}
条款：{', '.join(metadata.get('articles', []))}

请严格按照系统指令输出 JSON。"""

    for attempt in range(3):
        try:
            response = llm.client.chat.completions.create(
                model=llm.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=1024,
            )

            content = response.choices[0].message.content
            if not content or not content.strip():
                return {"triples": []}

            result = _parse_json_response(content)

            if "triples" not in result:
                return {"triples": []}

            return result

        except (json.JSONDecodeError, ValueError, KeyError, TypeError) as e:
            if attempt < 2:
                time.sleep(2)
                continue
            return {"triples": []}


def _process_chunk(llm, chunk):
    text = chunk["text"]
    metadata = chunk["metadata"]
    llm_result = extract_single(llm, text, metadata)
    rule_result = extract_numerical_fallback(text)
    merged = merge_triples(llm_result, rule_result)
    triples = filter_triples(merged)
    return metadata, triples


def _make_sources(metadata):
    filename = metadata.get("filename", "")
    chapter = metadata.get("chapter", "")
    section = metadata.get("section", "")
    articles = metadata.get("articles", [])
    if articles:
        for a in articles:
            yield {"filename": filename, "chapter": chapter, "section": section, "clause": a}
    else:
        yield {"filename": filename, "chapter": chapter, "section": section, "clause": ""}


def main(write_to_neo4j: bool = False, progress_callback=None):
    print("=" * 60)
    print("  建筑规范三元组提取工具")
    print("=" * 60)

    print("\n[1/4] 加载切分数据...")
    chunks = load_chunks()
    print(f"  共加载 {len(chunks)} 个文本块")

    print("\n[2/4] 初始化 DeepSeek 客户端...")
    llm = init_client()
    print(f"  模型：{llm.model}")

    print("\n[3/4] 开始并发抽取三元组...")
    filtered_results = []
    success_count = 0
    empty_count = 0
    total = len(chunks)
    max_workers = int(os.getenv("GRAPH_EXTRACT_WORKERS", "8"))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_process_chunk, llm, chunk): i
            for i, chunk in enumerate(chunks)
        }
        completed = 0
        for future in as_completed(futures):
            metadata, triples = future.result()
            completed += 1
            section = metadata.get("section", "")
            articles = metadata.get("articles", [])

            print(f"\r  已完成 [{completed}/{total}] {section or '无章节'} {articles}", end="")

            if progress_callback:
                progress_callback(completed, total, "LLM 抽取三元组")

            filtered_results.append({"metadata": metadata, "triples": triples})

            if triples:
                success_count += 1
            else:
                empty_count += 1

    print()

    print("\n[4/4] 聚合与保存...")
    entity_sources = {}
    all_relations = []

    def _add_entity(name, label, sources):
        if name not in entity_sources:
            entity_sources[name] = {"label": label, "sources": []}
        for src in sources:
            if src not in entity_sources[name]["sources"]:
                entity_sources[name]["sources"].append(src)

    for r in filtered_results:
        metadata = r["metadata"]
        sources = list(_make_sources(metadata))
        for trip in r["triples"]:
            pred = trip["predicate"]
            if pred == "必须设置":
                subj_label, obj_label = "建筑部位", "安全设施"
            else:
                subj_label, obj_label = "建筑部位", "规范数值"
            _add_entity(trip["subject"], subj_label, sources)
            _add_entity(trip["object"], obj_label, sources)
            all_relations.append({
                "from": trip["subject"],
                "rel": pred,
                "to": trip["object"],
                "sources": sources,
            })

    nodes = [
        {"name": name, "label": info["label"], "sources": info["sources"]}
        for name, info in entity_sources.items()
    ]

    NODES_PATH = os.path.join(OUTPUT_DIR, "nodes.json")
    RELATIONS_PATH = os.path.join(OUTPUT_DIR, "relations.json")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(filtered_results, f, ensure_ascii=False, indent=2)
    with open(NODES_PATH, "w", encoding="utf-8") as f:
        json.dump(nodes, f, ensure_ascii=False, indent=2)
    with open(RELATIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(all_relations, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"  抽取完成！")
    print(f"  处理文本块：{total}")
    print(f"  提取到三元组的块：{success_count}")
    print(f"  未提取到三元组的块：{empty_count}")
    print(f"")
    print(f"  唯一节点：{len(nodes)}")
    print(f"  关系总条数：{len(all_relations)}")
    print(f"")
    print(f"  原始输出（含元数据）：{OUTPUT_PATH}")
    print(f"  节点文件：{NODES_PATH}")
    print(f"  关系文件：{RELATIONS_PATH}")
    print(f"{'=' * 60}")

    if write_to_neo4j:
        from backend.indexing.write_neo4j import main as neo4j_main
        neo4j_main()


if __name__ == "__main__":
    import sys
    main(write_to_neo4j="--neo4j" in sys.argv)
