"""MCP tools: Brave Search — web, web context (LLM grounding), and image search.

Implementation stays plain testable functions; SDK registration lives in
registry.py as with the other tools.

Reference: brave_search_agent_tools.md (api.search.brave.com/res/v1).
Includes a monthly quota counter so a free tier (US$5/month ≈ 1000 calls)
is never exceeded.
"""

import json
import threading
from datetime import date
from pathlib import Path
from random import random
from time import sleep
from typing import Any

import requests

from src.config import BASE_DIR, Config

_BASE = "https://api.search.brave.com/res/v1"
_WEB_SEARCH = "/web/search"
_LLM_CONTEXT = "/llm/context"
_IMAGE_SEARCH = "/images/search"

_DEFAULT_TIMEOUT = 30.0
_MAX_RETRIES = 3

# ──────────────────────── monthly quota counter ────────────────────────
# Persist one JSON file per month under data/, so a free tier quota is never
# exceeded even across process restarts. Guarded by a lock for concurrent
# Discord events.
_QUOTA_LOCK = threading.Lock()


def _quota_path() -> Path:
    ym = date.today().strftime("%Y-%m")
    return BASE_DIR / "data" / f"brave_quota_{ym}.json"


def _read_quota(path: Path) -> int:
    try:
        return int(json.loads(path.read_text()).get("count", 0))
    except (OSError, ValueError, json.JSONDecodeError):
        return 0


def _write_quota(path: Path, count: int) -> None:
    path.write_text(json.dumps({"count": count}))


def try_consume_quota(limit: int | None = None) -> tuple[bool, int, int]:
    """Attempt to reserve one monthly Brave call.

    Returns (allowed, used_so_far, limit). When limit is None (unlimited) it
    always allows and returns (True, used, -1). Refused calls do NOT increment.
    """
    if limit is None:
        return True, _read_quota(_quota_path()), -1
    with _QUOTA_LOCK:
        path = _quota_path()
        used = _read_quota(path)
        if used >= limit:
            return False, used, limit
        _write_quota(path, used + 1)
        return True, used + 1, limit


def _headers(key: str) -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": key,
    }


def _request_with_retry(
    path: str, params: dict[str, Any], key: str, timeout: float
) -> dict:
    """GET with bounded retry/backoff for 429 and transient 5xx errors."""
    url = f"{_BASE}{path}"
    for attempt in range(_MAX_RETRIES):
        try:
            resp = requests.get(
                url, params=params, headers=_headers(key), timeout=timeout
            )
            if resp.status_code in (429, 500, 502, 503, 504):
                if attempt == _MAX_RETRIES - 1:
                    resp.raise_for_status()
                sleep((2**attempt) + random())
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException:
            if attempt == _MAX_RETRIES - 1:
                raise
            sleep((2**attempt) + random())
    raise RuntimeError("Unreachable")  # pragma: no cover


# ─────────────────────────── normalization helpers ──────────────────────────


def normalize_web_results(data: dict) -> list[dict]:
    """Normalize /web/search response into {title, url, snippet, extra_snippets}."""
    results = []
    for item in data.get("web", {}).get("results", []):
        results.append(
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "snippet": item.get("description"),
                "extra_snippets": item.get("extra_snippets", []),
            }
        )
    return results


def normalize_image_results(data: dict) -> list[dict]:
    """Normalize /images/search response into {title, thumbnail_url, image_url,
    source_url, width, height}."""
    results = []
    for item in data.get("results", []):
        meta = item.get("meta_url") or {}
        results.append(
            {
                "title": item.get("title"),
                "description": item.get("description"),
                # Brave serves thumbnails through its image proxy
                "thumbnail_url": item.get("thumbnail", {}).get("src")
                if isinstance(item.get("thumbnail"), dict)
                else None,
                # original image URL from the source site
                "image_url": (item.get("properties") or {}).get("url"),
                # source site / hostname for attribution
                "source_url": meta.get("netloc") or meta.get("hostname"),
                "source_favicon": meta.get("favicon"),
                "width": (item.get("properties") or {}).get("width"),
                "height": (item.get("properties") or {}).get("height"),
            }
        )
    return results


def _format_web_results(results: list[dict]) -> str:
    if not results:
        return "沒有找到相關網頁結果。"
    lines = [f"找到 {len(results)} 筆網頁結果，顯示前 {len(results)} 筆：\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title'] or 'N/A'}")
        lines.append(f"   網址：{r['url'] or 'N/A'}")
        if r.get("snippet"):
            lines.append(f"   摘要：{r['snippet']}")
        lines.append("")
    return "\n".join(lines)


def _format_context_results(sources: list[dict]) -> str:
    if not sources:
        return "沒有找到相關的網頁內容。"
    lines = [f"擷取到 {len(sources)} 個來源的內容：\n"]
    for i, s in enumerate(sources, 1):
        lines.append(f"{i}. {s['title'] or 'N/A'}")
        lines.append(f"   來源：{s['url'] or 'N/A'}")
        content = (s.get("content") or "").strip()
        if content:
            lines.append(f"   內容：{content}")
        lines.append("")
    return "\n".join(lines)


def _format_image_results(results: list[dict]) -> str:
    if not results:
        return "沒有找到相關圖片。"
    lines = [f"找到 {len(results)} 張圖片：\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title'] or 'N/A'}")
        lines.append(f"   圖片網址：{r['image_url'] or 'N/A'}")
        if r.get("source_url"):
            lines.append(f"   來源：{r['source_url']}")
        if r.get("width") and r.get("height"):
            lines.append(f"   尺寸：{r['width']} x {r['height']}")
        lines.append("")
    return "\n".join(lines)


# ────────────────────────────────── impls ───────────────────────────────────


def _build_error(msg: str) -> dict[str, Any]:
    return {"error": msg, "formatted": msg, "results": [], "total": None}


async def web_search_impl(
    query: str,
    search_type: str = "web",
    count: int = 8,
    max_tokens: int = 4096,
    freshness: str | None = None,
    country: str | None = None,
    search_lang: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Implementation backing the registered MCP tools.

    search_type: "web" | "context" | "image". Returns a stable normalized dict
    plus a pre-formatted text block for the agent, preserving source URLs.
    """
    key = api_key or Config.BRAVE_SEARCH_API_KEY
    if not key:
        return _build_error(
            "BRAVE_SEARCH_API_KEY 未設定。請在 .env 加上你的 Brave Search API key。"
        )

    allowed, used, limit = try_consume_quota(Config.BRAVE_MONTHLY_LIMIT)
    if not allowed:
        return _build_error(
            f"本月 Brave 搜尋額度（{limit} 次）已用完（已用 {used} 次）。"
            "請等待下個月重置，或調高 BRAVE_MONTHLY_LIMIT。"
        )

    stype = (search_type or "web").lower()
    params: dict[str, Any] = {"q": query}
    if country:
        params["country"] = country
    if search_lang:
        params["search_lang"] = search_lang
    if freshness:
        params["freshness"] = freshness

    try:
        if stype == "image":
            params["count"] = min(max(count, 1), 200)
            params["safesearch"] = "strict"
            data = _request_with_retry(
                _IMAGE_SEARCH, params, key, _DEFAULT_TIMEOUT
            )
            results = normalize_image_results(data)
            pretty = _format_image_results(results)
            return {
                "query": query,
                "search_type": "image",
                "results": results,
                "total": len(results),
                "formatted": pretty,
            }
        if stype == "context":
            params.update(
                {
                    "count": 10,
                    "maximum_number_of_urls": min(max(count, 1), 10),
                    "maximum_number_of_tokens": min(
                        max(max_tokens, 1024), 8192
                    ),
                    "enable_source_metadata": True,
                }
            )
            data = _request_with_retry(
                _LLM_CONTEXT, params, key, _DEFAULT_TIMEOUT
            )
            sources = _normalize_context(data)
            pretty = _format_context_results(sources)
            return {
                "query": query,
                "search_type": "context",
                "results": sources,
                "total": len(sources),
                "formatted": pretty,
            }

        # default: web
        params["count"] = min(max(count, 1), 20)
        data = _request_with_retry(_WEB_SEARCH, params, key, _DEFAULT_TIMEOUT)
        results = normalize_web_results(data)
        pretty = _format_web_results(results)
        return {
            "query": query,
            "search_type": "web",
            "results": results,
            "total": len(results),
            "formatted": pretty,
        }
    except requests.HTTPError as exc:
        status = getattr(exc.response, "status_code", None)
        detail = ""
        if status == 401 or status == 403:
            detail = "（Brave API key 無效或無權限）"
        elif status == 429:
            detail = "（超出額度或頻率限制，請稍後再試）"
        elif status and 500 <= status < 600:
            detail = "（Brave 伺服器暫時錯誤）"
        msg = f"Brave 搜尋失敗（HTTP {status}）{detail}"
        return _build_error(msg)
    except requests.RequestException as exc:
        return _build_error(f"連線 Brave 失敗：{exc}")


def _normalize_context(data: dict) -> list[dict]:
    """Extract grounding chunks + source metadata, keyed by URL.

    Brave's grounding chunks expose ``snippets`` (a list of strings), and the
    ``sources`` map carries per-URL metadata (title / hostname / snippet).
    """
    sources_map: dict[str, dict] = {}
    for chunk in data.get("grounding", {}).get("generic", []):
        url = chunk.get("url")
        if not url:
            continue
        src = sources_map.setdefault(
            url,
            {
                "url": url,
                "title": chunk.get("title") or url,
                "content": [],
                "hostname": None,
                "favicon": None,
            },
        )
        for text in chunk.get("snippets") or []:
            if text:
                src["content"].append(text)
    # Attach source metadata if Brave enriched it
    for url, meta in (data.get("sources") or {}).items():
        src = sources_map.get(url)
        if not src:
            continue
        if meta.get("title"):
            src["title"] = meta["title"]
        src["hostname"] = meta.get("hostname")
        src["favicon"] = meta.get("favicon")

    sources: list[dict] = []
    for url, src in sources_map.items():
        joined = "\n\n".join(src["content"])
        # Cap each source's displayed content (approx char len for CJK)
        max_chars = 4000
        if len(joined) > max_chars:
            joined = joined[:max_chars] + "…"
        sources.append(
            {
                "url": src["url"],
                "title": src["title"],
                "content": joined,
                "hostname": src["hostname"],
                "favicon": src["favicon"],
            }
        )
    return sources
