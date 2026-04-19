"""MCP tool: fetch & analyze a 104 job posting (or bare company+title query).

Unlike the previous workflow which also made a second LLM call to generate a
report, this tool just returns the extracted webpage content; the agent's
surrounding conversation handles analysis and formatting itself.
"""

import re
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from playwright.async_api import (
    Page,
    TimeoutError as PlaywrightTimeout,
    async_playwright,
)


URL_RE = re.compile(r"https?://[^\s]+")


def extract_url_from_query(query: str) -> str | None:
    m = URL_RE.search(query)
    return m.group(0) if m else None


def validate_url_security(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    if host in ("localhost", "127.0.0.1", "0.0.0.0"):
        return False
    if host.startswith(("10.", "192.168.")):
        return False
    if host.startswith("172."):
        try:
            second = int(host.split(".")[1])
            if 16 <= second <= 31:
                return False
        except (ValueError, IndexError):
            pass
    return True


def _is_dynamic(url: str) -> bool:
    return "104.com.tw" in url


async def _extract_104_dynamic(page: Page) -> str:
    await page.wait_for_selector("body", timeout=15000)
    await page.wait_for_timeout(2000)
    body_text = await page.locator("body").inner_text()
    lines = [ln.strip() for ln in body_text.split("\n") if ln.strip()]

    parts: list[str] = []
    try:
        h1 = await page.locator("h1").first.inner_text()
        if h1 and len(h1) < 100:
            parts.append(f"【職位名稱】\n{h1.strip()}\n")
    except Exception:
        pass

    for line in lines[:40]:
        if ("股份有限公司" in line or "有限公司" in line) and len(line) < 60:
            parts.append(f"【公司名稱】\n{line}\n")
            break

    sections = {
        "工作內容": ("工作內容", "職務類別"),
        "工作待遇": ("工作待遇", "工作性質"),
        "條件要求": ("條件要求", "公司環境照片"),
        "福利制度": ("福利制度", "聯絡方式"),
    }
    for name, (start, end) in sections.items():
        body = _extract_section(lines, start, end)
        if body:
            parts.append(f"【{name}】\n{body}\n")

    if parts:
        return "\n".join(parts)
    return "\n".join(lines[:80])


def _extract_section(lines: list[str], start: str, end: str) -> str:
    out: list[str] = []
    capturing = False
    for line in lines:
        if start in line:
            capturing = True
            if line.strip() != start:
                out.append(line)
            continue
        if capturing:
            if end in line:
                break
            out.append(line)
    return "\n".join(out).strip()


async def _fetch_dynamic(url: str) -> str | None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            await context.route(
                "**/*.{png,jpg,jpeg,gif,svg,css,font,woff,woff2}",
                lambda route: route.abort(),
            )
            page = await context.new_page()
            page.set_default_timeout(30000)
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                return await _extract_104_dynamic(page)
            except PlaywrightTimeout:
                return None
        finally:
            await browser.close()


def _fetch_static(url: str) -> str | None:
    try:
        resp = requests.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
            },
            timeout=10,
            verify=True,
        )
        resp.raise_for_status()
    except requests.RequestException:
        return None

    soup = BeautifulSoup(resp.content, "html.parser")
    for tag in soup(["script", "style", "header", "footer", "nav"]):
        tag.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(separator=" ", strip=True))
    return text[:2000]


async def fetch_webpage_content(url: str) -> str | None:
    if not validate_url_security(url):
        return None
    if _is_dynamic(url):
        return await _fetch_dynamic(url)
    return _fetch_static(url)


async def analyze_104_job_impl(url_or_query: str) -> dict[str, Any]:
    """Return extracted webpage content if a URL is present, else just echo the query."""
    url = extract_url_from_query(url_or_query)
    content: str | None = None
    if url:
        content = await fetch_webpage_content(url)
    return {
        "query": url_or_query,
        "webpage_content": content,
    }
