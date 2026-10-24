"""Optional OpenAI suggestions for Smart Clean (user-supplied API key)."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import List


def suggest_with_openai(
    *,
    api_key: str,
    model: str,
    manufacturer: str,
    model_name: str,
    packages: List[str],
) -> List[dict]:
    """Return list of {package, tier, reason}. Raises on HTTP/API errors."""
    if not api_key:
        raise ValueError("Chưa cấu hình OpenAI API key")
    pkgs = packages[:100]
    system = (
        "Bạn là trợ lý debloat Android TV. Trả về JSON thuần: "
        '{"suggestions":[{"package":"...","tier":"recommend|review|skip","reason":"..."}]}. '
        "tier=recommend chỉ cho app bloat/quảng cáo/demo an toàn tắt; "
        "review cho app có thể ảnh hưởng launcher/Google/HDMI; "
        "skip cho app quan trọng hoặc không chắc. "
        "Không gợi ý tắt com.android.systemui, settings, packageinstaller, launcher đang dùng."
    )
    user = json.dumps(
        {
            "manufacturer": manufacturer,
            "model": model_name,
            "packages": pkgs,
            "note": "Chỉ phân loại các package trong danh sách.",
        },
        ensure_ascii=False,
    )
    body = json.dumps(
        {
            "model": model or "gpt-4o-mini",
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"OpenAI HTTP {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Không kết nối OpenAI: {e}") from e

    content = (
        payload.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        raise RuntimeError("OpenAI trả về JSON không hợp lệ") from e
    rows = parsed.get("suggestions") if isinstance(parsed, dict) else None
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict)]


def ping_openai(*, api_key: str) -> None:
    """Verify API key can reach OpenAI (models list)."""
    if not api_key:
        raise ValueError("Chưa cấu hình OpenAI API key")
    req = urllib.request.Request(
        "https://api.openai.com/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            if resp.status >= 400:
                raise RuntimeError(f"OpenAI HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"OpenAI HTTP {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Không kết nối OpenAI: {e}") from e
