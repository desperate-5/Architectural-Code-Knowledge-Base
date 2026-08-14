import io
import os
import time
import zipfile
from urllib.parse import quote

import requests

from backend.shared.settings import Settings

POLL_INTERVAL = 3
POLL_TIMEOUT = 600
DONE_STATES = {"done"}
FAILED_STATES = {"failed"}


class MineruClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        settings = Settings()
        self.token = settings.MINERU_API_TOKEN
        self.base_url = settings.MINERU_API_BASE.rstrip("/")
        self.model_version = settings.MINERU_MODEL_VERSION

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }

    def _ensure_token(self):
        if not self.token:
            raise ValueError(
                "MINERU_API_TOKEN 未配置，请在 .env 中设置（从 https://mineru.net/apiManage/token 获取）"
            )

    def _check(self, resp: requests.Response) -> dict:
        if resp.status_code >= 400:
            raise RuntimeError(f"MinerU API HTTP {resp.status_code}: {resp.text[:500]}")
        payload = resp.json()
        if not isinstance(payload, dict):
            raise RuntimeError(f"MinerU API 返回非对象: {payload!r}")
        code = payload.get("code", 0)
        if code not in (0, "0", None):
            raise RuntimeError(
                f"MinerU API 业务错误: {payload.get('msg')} (code={code})"
            )
        return payload.get("data") or {}

    def _get_upload_urls(self, name: str) -> tuple[str, str]:
        self._ensure_token()
        resp = requests.post(
            f"{self.base_url}/file-urls/batch",
            headers=self._headers(),
            json={
                "files": [{"name": name}],
                "model_version": self.model_version,
                "language": "ch",
                "enable_table": True,
                "enable_formula": True,
            },
            timeout=60,
        )
        data = self._check(resp)
        batch_id = str(data.get("batch_id") or "")
        file_urls = data.get("file_urls") or []
        if not batch_id or not file_urls:
            raise RuntimeError(f"MinerU API 未返回 batch_id/上传地址: {data}")
        first = file_urls[0]
        if isinstance(first, dict):
            upload_url = str(first.get("url") or first.get("file_url") or "")
        else:
            upload_url = str(first)
        if not upload_url:
            raise RuntimeError(f"MinerU API 上传地址为空: {data}")
        return batch_id, upload_url

    def _upload_file(self, url: str, path: str):
        with open(path, "rb") as f:
            resp = requests.put(
                url,
                data=f,
                headers={"Content-Length": str(os.path.getsize(path))},
                timeout=300,
            )
        if resp.status_code >= 300:
            raise RuntimeError(f"MinerU 上传失败 HTTP {resp.status_code}: {resp.text[:500]}")

    def _poll_batch(self, batch_id: str) -> dict:
        url = f"{self.base_url}/extract-results/batch/{quote(batch_id, safe='')}"
        start = time.time()
        while True:
            resp = requests.get(url, headers=self._headers(), timeout=60)
            data = self._check(resp)
            results = data.get("extract_result")
            if isinstance(results, dict):
                results = [results]
            if isinstance(results, list) and results:
                selected = results[0]
                state = str(selected.get("state") or "").lower()
                if state in DONE_STATES:
                    return selected
                if state in FAILED_STATES:
                    err = selected.get("err_msg") or selected.get("error") or selected
                    raise RuntimeError(f"MinerU 解析任务失败: {err}")
            if time.time() - start > POLL_TIMEOUT:
                raise TimeoutError(
                    f"MinerU 解析任务超时（>{POLL_TIMEOUT}s），batch_id={batch_id}"
                )
            time.sleep(POLL_INTERVAL)

    def _download_markdown(self, task_data: dict) -> str:
        # Standard API 返回 ZIP（full_zip_url），内含 *.md；兼容直接 md_url / md_content
        zip_url = task_data.get("full_zip_url") or task_data.get("zip_url")
        if zip_url:
            resp = requests.get(zip_url, timeout=300)
            if resp.status_code < 400:
                with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                    for name in zf.namelist():
                        if name.lower().endswith(".md"):
                            return zf.read(name).decode("utf-8", errors="ignore")
        result = task_data.get("extract_result") or {}
        md_url = (
            result.get("md_url")
            or task_data.get("md_url")
            or task_data.get("md_content_url")
        )
        if md_url:
            resp = requests.get(md_url, timeout=300)
            if resp.status_code < 400:
                return resp.content.decode("utf-8", errors="ignore")
        md_content = result.get("md_content") or task_data.get("md_content")
        if md_content:
            return md_content
        raise RuntimeError(f"未在任务结果中找到 Markdown 内容: {task_data}")

    def parse_pdf_to_markdown(self, pdf_path: str) -> str:
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")
        name = os.path.basename(pdf_path)

        print(f"  → 上传文件: {name}")
        batch_id, upload_url = self._get_upload_urls(name)
        self._upload_file(upload_url, pdf_path)

        print(f"  → 等待解析完成 (batch_id={batch_id})...")
        task_data = self._poll_batch(batch_id)

        print(f"  → 下载解析结果...")
        return self._download_markdown(task_data)
