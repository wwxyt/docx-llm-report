"""OpenAI 兼容接口的最小客户端（仅标准库，无 SDK 依赖）。"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request


class LLMError(RuntimeError):
    """模型调用或结果解析失败。"""


def _base_url() -> str:
    return os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")


def _model(model: str | None) -> str:
    return model or os.getenv("LLM_MODEL", "gpt-4o-mini")


def parse_json(text: str) -> dict:
    """兼容模型把 JSON 包在代码块里、或前后夹带解释的情况。"""
    text = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start:end + 1])
        raise


def _post(messages: list[dict], model: str | None, temperature: float, timeout: int) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise LLMError("未设置 OPENAI_API_KEY：先跑 `docxllm run --mock` 验证链路，或配置密钥后重试。")

    payload = {
        "model": _model(model),
        "messages": messages,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        f"{_base_url()}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"]


def chat_json(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.3,
    retries: int = 2,
    timeout: int = 180,
) -> dict:
    """调用模型并返回解析后的 JSON，失败自动重试。"""
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return parse_json(_post(messages, model, temperature, timeout))
        except LLMError:
            raise
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, IndexError) as exc:
            last = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            break
    raise LLMError(f"模型调用失败：{type(last).__name__}: {last}")
