# Brave Search Tools for a Self-Hosted LLM Agent

> Purpose: implement web and image search tools for a self-hosted LLM agent using the Brave Search API.
>
> Last verified: 2026-08-13 against Brave's official API documentation.

## 1. Scope

Implement these three tools:

1. `web_search` — standard ranked web search results.
2. `web_search_context` — web search with pre-extracted content optimized for LLM grounding.
3. `image_search` — image search results with thumbnails and original image/source URLs.

For a self-hosted small model, prefer `web_search_context` for questions where the model needs to **read web content and answer a question**. Use `web_search` when the agent needs **search-result metadata / URLs / snippets** or wants to choose sources itself. Use `image_search` when the user explicitly asks to find or show images.

Do **not** use Brave Answers as the primary agent tool for this project: Answers adds Brave's own answer-generation layer, while this architecture should keep reasoning and final answer generation in our own model.

---

## 2. Authentication and Configuration

All three endpoints use the same Brave Search API key.

Store the key in an environment variable:

```bash
export BRAVE_SEARCH_API_KEY="<your-key>"
```

Never hard-code the key in source code or expose it to the LLM.

Common request header:

```http
X-Subscription-Token: <BRAVE_SEARCH_API_KEY>
Accept: application/json
Accept-Encoding: gzip
```

Suggested Python dependencies:

```bash
pip install requests
```

Base URL:

```text
https://api.search.brave.com/res/v1
```

---

## 3. API Summary

| Tool | Endpoint | Best use |
|---|---|---|
| `web_search` | `GET /web/search` | Ranked SERP results, URLs, snippets, metadata |
| `web_search_context` | `GET or POST /llm/context` | AI agent grounding / RAG / direct LLM context |
| `image_search` | `GET /images/search` | Finding images, thumbnails, original image URLs |

Current Brave Search plan snapshot:

- Search plan: **US$5 / 1,000 requests**
- Includes **US$5 free credits each month**
- Search plan capacity: **50 queries/sec**

Pricing and limits can change, so production code should not assume the billing plan is permanent.

---

# 4. Tool 1 — `web_search`

## Purpose

Use standard Brave Web Search when the agent needs a conventional search-engine result set:

- titles
- URLs
- descriptions/snippets
- ranking
- source metadata
- pagination
- optional extra snippets

This is useful when the agent or orchestrator wants to select sources itself.

## Endpoint

```http
GET https://api.search.brave.com/res/v1/web/search
```

## Important parameters

| Parameter | Type | Notes |
|---|---|---|
| `q` | string | Required search query |
| `count` | integer | Results per page; max `20`, default `20` |
| `offset` | integer | Page offset; `0`-based, max `9` |
| `country` | string | Two-character country code, e.g. `US`, `TW`, `JP` |
| `search_lang` | string | Search language, e.g. `en`, `zh-hant`, depending on supported values |
| `safesearch` | string | `off`, `moderate`, `strict`; default is `moderate` |
| `freshness` | string | `pd`, `pw`, `pm`, `py`, or custom date range |
| `extra_snippets` | boolean | If `true`, may return up to 5 extra excerpts per result |

Freshness values:

```text
pd = last 24 hours
pw = last 7 days
pm = last 31 days
py = last 365 days
```

Custom range example:

```text
2026-08-01to2026-08-13
```

Search operators can be embedded directly in `q`, for example:

```text
site:nvidia.com Blackwell
filetype:pdf "AI security"
"exact phrase"
javascript -jquery
```

## cURL example

```bash
curl --compressed \
  "https://api.search.brave.com/res/v1/web/search?q=NVIDIA+Blackwell&count=5&freshness=pw" \
  -H "Accept: application/json" \
  -H "Accept-Encoding: gzip" \
  -H "X-Subscription-Token: ${BRAVE_SEARCH_API_KEY}"
```

## Python example

```python
import os
import requests

BRAVE_API_KEY = os.environ["BRAVE_SEARCH_API_KEY"]

def web_search(
    query: str,
    count: int = 5,
    country: str | None = None,
    search_lang: str | None = None,
    freshness: str | None = None,
) -> dict:
    params = {
        "q": query,
        "count": min(max(count, 1), 20),
    }

    if country:
        params["country"] = country
    if search_lang:
        params["search_lang"] = search_lang
    if freshness:
        params["freshness"] = freshness

    response = requests.get(
        "https://api.search.brave.com/res/v1/web/search",
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": BRAVE_API_KEY,
        },
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()
```

## Recommended normalized tool output

Do not send the entire raw API response to a small model unless necessary. Normalize it first:

```json
{
  "query": "NVIDIA Blackwell latest news",
  "results": [
    {
      "title": "Example title",
      "url": "https://example.com/article",
      "snippet": "Relevant search-result description..."
    }
  ]
}
```

Suggested normalization:

```python
def normalize_web_results(data: dict) -> list[dict]:
    results = []

    for item in data.get("web", {}).get("results", []):
        results.append({
            "title": item.get("title"),
            "url": item.get("url"),
            "snippet": item.get("description"),
            "extra_snippets": item.get("extra_snippets", []),
        })

    return results
```

## Pagination

Brave recommends checking:

```json
{
  "query": {
    "more_results_available": true
  }
}
```

before requesting another page.

Do not blindly request all offsets.

---

# 5. Tool 2 — `web_search_context`

## Purpose

This is the **recommended default web tool for our self-hosted LLM agent**.

Brave searches the web and returns pre-extracted, relevance-filtered chunks designed for machine consumption.

Conceptually:

```text
query
  ↓
Brave Search
  ↓
source selection
  ↓
page content extraction
  ↓
relevant chunks
  ↓
our self-hosted LLM
  ↓
answer
```

This avoids requiring the small model or backend to:

1. inspect many search-result snippets,
2. fetch every page itself,
3. extract HTML,
4. remove page noise,
5. select relevant passages.

## Endpoint

GET:

```http
GET https://api.search.brave.com/res/v1/llm/context
```

POST is also supported:

```http
POST https://api.search.brave.com/res/v1/llm/context
```

## Important parameters

| Parameter | Range/default | Meaning |
|---|---:|---|
| `q` | required | Search query; max 400 characters / 50 words |
| `count` | 1–50, default 20 | Search results considered for context |
| `maximum_number_of_urls` | 1–50, default 20 | Max unique URLs included |
| `maximum_number_of_tokens` | 1024–32768, default 8192 | Approximate total context token budget |
| `maximum_number_of_tokens_per_url` | 512–8192, default 4096 | Per-source token budget |
| `maximum_number_of_snippets` | 1–256, default 50 | Requested chunk limit |
| `maximum_number_of_snippets_per_url` | 1–100, default 50 | Requested per-URL chunk limit |
| `context_threshold_mode` | enum | Relevance threshold behavior |
| `freshness` | string | `pd`, `pw`, `pm`, `py`, or custom range |
| `country` | string | Search market |
| `search_lang` | string | Search language |
| `safesearch` | enum | `off`, `moderate`, `strict` |
| `enable_source_metadata` | boolean | Include richer source metadata |
| `spellcheck` | boolean | Default `true` |

As of the 2026-07-31 Brave content pipeline update, snippet-count fields may no longer strictly constrain the response when the token budget allows additional snippets. Treat the **token budget** as the main control for model context size.

## Recommended presets

### Fast factual lookup

```json
{
  "count": 5,
  "maximum_number_of_urls": 5,
  "maximum_number_of_tokens": 2048
}
```

### Normal agent search

```json
{
  "count": 10,
  "maximum_number_of_urls": 5,
  "maximum_number_of_tokens": 4096,
  "maximum_number_of_tokens_per_url": 2048,
  "enable_source_metadata": true
}
```

### Broader research query

```json
{
  "count": 20,
  "maximum_number_of_urls": 10,
  "maximum_number_of_tokens": 8192,
  "enable_source_metadata": true
}
```

Avoid giving a small model 32K search context by default. Start small and increase only when the task requires it.

## cURL example

```bash
curl --compressed \
  "https://api.search.brave.com/res/v1/llm/context?q=NVIDIA+Blackwell+latest+production+status&count=10&maximum_number_of_urls=5&maximum_number_of_tokens=4096&enable_source_metadata=true" \
  -H "Accept: application/json" \
  -H "Accept-Encoding: gzip" \
  -H "X-Subscription-Token: ${BRAVE_SEARCH_API_KEY}"
```

## Python example

```python
import os
import requests

BRAVE_API_KEY = os.environ["BRAVE_SEARCH_API_KEY"]

def web_search_context(
    query: str,
    count: int = 10,
    max_urls: int = 5,
    max_tokens: int = 4096,
    freshness: str | None = None,
    country: str | None = None,
    search_lang: str | None = None,
) -> dict:
    params = {
        "q": query,
        "count": min(max(count, 1), 50),
        "maximum_number_of_urls": min(max(max_urls, 1), 50),
        "maximum_number_of_tokens": min(max(max_tokens, 1024), 32768),
        "enable_source_metadata": True,
    }

    if freshness:
        params["freshness"] = freshness
    if country:
        params["country"] = country
    if search_lang:
        params["search_lang"] = search_lang

    response = requests.get(
        "https://api.search.brave.com/res/v1/llm/context",
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": BRAVE_API_KEY,
        },
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()
```

## Response

The main response areas are:

```json
{
  "grounding": {
    "generic": [],
    "map": []
  },
  "sources": {}
}
```

`grounding.generic` contains the web-grounding content.

`sources` contains metadata for referenced URLs. With `enable_source_metadata=true`, Brave can enrich source entries with fields such as:

- site name
- favicon
- thumbnail
- description

The extraction may contain plain text or structured / JSON-serialized data such as tables, schemas, or code. Do not assume every chunk is plain prose.

## Agent-facing normalized format

Prefer giving the model a stable internal schema independent of Brave's raw response:

```json
{
  "query": "NVIDIA Blackwell latest production status",
  "sources": [
    {
      "url": "https://example.com/source",
      "title": "Source title",
      "content": "Relevant extracted context..."
    }
  ]
}
```

Preserve source URLs so the final answer can cite sources.

---

# 6. Tool 3 — `image_search`

## Purpose

Use this tool when the user explicitly wants images, examples include:

```text
"Find images of NVIDIA Rubin."
"Show me pictures of H100 servers."
"Find reference images of a Japanese-style room."
```

This endpoint searches existing images on the web. It does **not** generate images.

## Endpoint

```http
GET https://api.search.brave.com/res/v1/images/search
```

## Important parameters

| Parameter | Type | Notes |
|---|---|---|
| `q` | string | Required search query |
| `count` | integer | Default 50, max 200 |
| `country` | string | Geographic preference |
| `search_lang` | string | Language preference |
| `safesearch` | string | `strict` or `off`; default `strict` |
| `spellcheck` | boolean | Default `true` |

Image Search does not need normal page-style pagination for typical use. Request only the number of images the UI actually needs.

For an agent UI, start with:

```text
count = 4 to 12
```

rather than returning 50–200 images to the model.

## cURL example

```bash
curl --compressed \
  "https://api.search.brave.com/res/v1/images/search?q=NVIDIA+Rubin&count=8&safesearch=strict" \
  -H "Accept: application/json" \
  -H "Accept-Encoding: gzip" \
  -H "X-Subscription-Token: ${BRAVE_SEARCH_API_KEY}"
```

## Python example

```python
import os
import requests

BRAVE_API_KEY = os.environ["BRAVE_SEARCH_API_KEY"]

def image_search(
    query: str,
    count: int = 8,
    country: str | None = None,
    search_lang: str | None = None,
) -> dict:
    params = {
        "q": query,
        "count": min(max(count, 1), 200),
        "safesearch": "strict",
    }

    if country:
        params["country"] = country
    if search_lang:
        params["search_lang"] = search_lang

    response = requests.get(
        "https://api.search.brave.com/res/v1/images/search",
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": BRAVE_API_KEY,
        },
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()
```

## Typical result data

Image results can include:

- title
- description
- thumbnail URL
- source page URL
- original image URL
- width / height when available
- publisher/source information

Brave's returned thumbnail is served through Brave's image proxy. The `properties.url` field can contain the original image URL from the source site.

## Recommended normalized format

```json
{
  "query": "NVIDIA Rubin",
  "images": [
    {
      "title": "NVIDIA Rubin...",
      "thumbnail_url": "https://...",
      "image_url": "https://...",
      "source_url": "https://...",
      "width": 1920,
      "height": 1080
    }
  ]
}
```

The LLM generally does **not** need image binary data. Return URLs and metadata to the orchestrator/UI.

---

# 7. Recommended Agent Tool Schemas

Expose narrow, easy-to-select tools to the small model.

## `web_search`

```json
{
  "name": "web_search",
  "description": "Search the public web and return ranked pages with titles, URLs, and short snippets. Use when you need to find sources, pages, or URLs rather than read detailed web context.",
  "parameters": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "Concise web search query"
      },
      "max_results": {
        "type": "integer",
        "minimum": 1,
        "maximum": 20,
        "default": 5
      },
      "freshness": {
        "type": "string",
        "enum": ["pd", "pw", "pm", "py"],
        "description": "Optional time filter: past day/week/month/year"
      }
    },
    "required": ["query"]
  }
}
```

## `web_search_context`

```json
{
  "name": "web_search_context",
  "description": "Search the public web and return relevant extracted content from multiple sources for answering current or factual questions. Prefer this tool when you need web information to reason or answer.",
  "parameters": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "Concise search query, not the entire conversation"
      },
      "max_urls": {
        "type": "integer",
        "minimum": 1,
        "maximum": 10,
        "default": 5
      },
      "max_tokens": {
        "type": "integer",
        "minimum": 1024,
        "maximum": 8192,
        "default": 4096
      },
      "freshness": {
        "type": "string",
        "enum": ["pd", "pw", "pm", "py"]
      }
    },
    "required": ["query"]
  }
}
```

The application intentionally exposes a smaller range than Brave's API maximum so a small model cannot accidentally request huge contexts.

## `image_search`

```json
{
  "name": "image_search",
  "description": "Search the public web for existing images. Use only when the user asks to find, show, view, or search for images or visual references.",
  "parameters": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "Image search query"
      },
      "max_results": {
        "type": "integer",
        "minimum": 1,
        "maximum": 20,
        "default": 8
      }
    },
    "required": ["query"]
  }
}
```

---

# 8. Tool Selection Policy

Teach the model this behavior:

```text
Need up-to-date / external factual information?
    |
    +-- Need to read information and answer?
    |       -> web_search_context
    |
    +-- Need to find pages / links / search results?
    |       -> web_search
    |
    +-- Need images / visual references?
            -> image_search
```

Examples:

```text
"What happened in NVIDIA's latest earnings?"
-> web_search_context

"Find the official NVIDIA CUDA documentation."
-> web_search

"Show me pictures of NVIDIA DGX GB200 racks."
-> image_search

"What is 2 + 2?"
-> no search
```

The model should not search when the answer is stable and already known unless the user asks for verification.

---

# 9. Recommended Small-Model Flow

```text
User
  ↓
Self-hosted LLM
  ↓
tool call
  ↓
Agent orchestrator
  ↓
Brave API
  ↓
normalize result
  ↓
Self-hosted LLM
  ↓
final answer + source URLs
```

For `web_search_context`, a good starting point is:

```text
max_urls = 5
max_tokens = 4096
```

For `web_search`:

```text
max_results = 5
```

For `image_search`:

```text
max_results = 8
```

Do not send the raw API response to the model if the response contains large amounts of metadata the model does not need.

---

# 10. Error Handling

Handle at least:

```text
400 Bad Request
403 Forbidden
404 Not Found
422 Unprocessable Entity
429 Too Many Requests
5xx transient server errors
network timeout
empty results
```

Recommended behavior:

```python
import random
import time
import requests

def request_with_retry(method, url, *, max_attempts=3, **kwargs):
    for attempt in range(max_attempts):
        try:
            response = requests.request(method, url, **kwargs)

            if response.status_code == 429 or response.status_code >= 500:
                if attempt == max_attempts - 1:
                    response.raise_for_status()

                delay = (2 ** attempt) + random.random()
                time.sleep(delay)
                continue

            response.raise_for_status()
            return response

        except requests.RequestException:
            if attempt == max_attempts - 1:
                raise

            delay = (2 ** attempt) + random.random()
            time.sleep(delay)

    raise RuntimeError("Unreachable")
```

Use approximately a 30-second network timeout.

For `web_search_context`, an empty:

```json
{
  "grounding": {
    "generic": []
  }
}
```

should be treated as "no relevant web context found", not as a parser failure.

---

# 11. Security Rules

The orchestrator owns the API key.

The LLM must never receive:

```text
BRAVE_SEARCH_API_KEY
X-Subscription-Token
```

The LLM should only produce tool arguments such as:

```json
{
  "query": "NVIDIA Blackwell latest news",
  "freshness": "pw"
}
```

Do not allow the model to control:

- arbitrary HTTP headers
- arbitrary URLs for the Brave API call
- API keys
- request timeout
- raw authentication fields

Also consider sanitizing sensitive internal information before turning user/internal data into a public-web search query.

---

# 12. Suggested Shared Client

A single backend client can implement all three endpoints.

```python
from __future__ import annotations

import os
from typing import Any

import requests


class BraveSearchClient:
    BASE_URL = "https://api.search.brave.com/res/v1"

    def __init__(self, api_key: str | None = None, timeout: float = 30.0):
        self.api_key = api_key or os.environ["BRAVE_SEARCH_API_KEY"]
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self.api_key,
        })

    def _get(self, path: str, params: dict[str, Any]) -> dict:
        response = self.session.get(
            f"{self.BASE_URL}{path}",
            params=params,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def web_search(
        self,
        query: str,
        max_results: int = 5,
        freshness: str | None = None,
    ) -> dict:
        params: dict[str, Any] = {
            "q": query,
            "count": min(max(max_results, 1), 20),
        }

        if freshness:
            params["freshness"] = freshness

        return self._get("/web/search", params)

    def web_search_context(
        self,
        query: str,
        max_urls: int = 5,
        max_tokens: int = 4096,
        freshness: str | None = None,
    ) -> dict:
        params: dict[str, Any] = {
            "q": query,
            "count": 10,
            "maximum_number_of_urls": min(max(max_urls, 1), 10),
            "maximum_number_of_tokens": min(max(max_tokens, 1024), 8192),
            "enable_source_metadata": True,
        }

        if freshness:
            params["freshness"] = freshness

        return self._get("/llm/context", params)

    def image_search(
        self,
        query: str,
        max_results: int = 8,
    ) -> dict:
        return self._get(
            "/images/search",
            {
                "q": query,
                "count": min(max(max_results, 1), 20),
                "safesearch": "strict",
            },
        )
```

The application should add normalization functions on top of this class before exposing responses to the model.

---

# 13. Implementation Requirements

The implementation is complete when all of these work:

- [ ] API key loaded only from server-side configuration / environment.
- [ ] `web_search` returns normalized title, URL, and snippet results.
- [ ] `web_search_context` returns extracted context plus source URLs.
- [ ] `image_search` returns thumbnail, image, and source URLs.
- [ ] Tool outputs use stable internal schemas instead of exposing Brave-specific raw JSON everywhere.
- [ ] All calls have timeouts.
- [ ] `429` and transient `5xx` errors have bounded retry/backoff.
- [ ] Empty results are handled without crashing the agent.
- [ ] Search calls and latency are logged for observability.
- [ ] Number of API calls per agent task is logged for cost monitoring.
- [ ] The LLM never sees the Brave API key.
- [ ] Source URLs are preserved so the final answer can cite where information came from.
- [ ] Unit tests mock Brave API responses rather than spending API quota.
- [ ] Integration tests cover each real endpoint with a small result count.

---

# 14. Recommended Initial Configuration

For the first implementation:

```yaml
brave_search:
  timeout_seconds: 30

  web:
    max_results: 5

  context:
    search_count: 10
    max_urls: 5
    max_tokens: 4096

  images:
    max_results: 8
    safesearch: strict
```

Start with these limits and tune them from real agent traces.

For a small self-hosted model, increasing search result volume is not automatically better. Prefer a small amount of high-relevance context.

---

# 15. Official Brave Documentation

- Brave Search API overview and pricing:  
  https://brave.com/search/api/

- Brave Web Search documentation:  
  https://api-dashboard.search.brave.com/app/documentation/web-search/get-started

- Brave Web Search API reference:  
  https://api-dashboard.search.brave.com/api-reference/web/search/get

- Brave LLM Context documentation:  
  https://api-dashboard.search.brave.com/documentation/services/llm-context

- Brave LLM Context API reference:  
  https://api-dashboard.search.brave.com/api-reference/summarizer/llm_context/get

- Brave Image Search documentation:  
  https://api-dashboard.search.brave.com/app/documentation/image-search/get-started

- Brave agent skills / endpoint overview:  
  https://api-dashboard.search.brave.com/documentation/resources/skills
