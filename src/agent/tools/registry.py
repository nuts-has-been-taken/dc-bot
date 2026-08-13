"""MCP server registry — wraps tool impls with @tool decorator and creates SDK servers.

The implementation functions (`search_104_jobs_impl`, `analyze_104_job_impl`, `DiscordToolset`
methods) live in their respective modules and stay testable as plain Python. This module
only handles SDK registration.
"""

from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from src.agent.tools.discord_mcp import DiscordToolset
from src.agent.tools.job_analysis_mcp import analyze_104_job_impl
from src.agent.tools.job_search_mcp import search_104_jobs_impl
from src.agent.tools.websearch_mcp import web_search_impl


def build_job_search_server():
    @tool(
        "search_104_jobs",
        "搜尋台灣 104 人力銀行職缺。支援中文地區名、職類名、學歷等參數。",
        {
            "keyword": str,
            "area": list,
            "job_category": list,
            "education": str,
            "sort_by": str,
            "salary_range": str,
            "posted_within_days": int,
        },
    )
    async def search_104_jobs(args: dict[str, Any]) -> dict[str, Any]:
        result = await search_104_jobs_impl(
            keyword=args.get("keyword", ""),
            area=args.get("area") or None,
            job_category=args.get("job_category") or None,
            education=args.get("education") or None,
            sort_by=args.get("sort_by") or None,
            salary_range=args.get("salary_range") or None,
            posted_within_days=args.get("posted_within_days") or None,
        )
        return {"content": [{"type": "text", "text": result["formatted"]}]}

    return create_sdk_mcp_server("job_search", version="1.0.0", tools=[search_104_jobs])


def build_job_analysis_server():
    @tool(
        "analyze_104_job",
        "抓取並解析 104 職缺頁面內容（或單純透傳查詢字串）。",
        {"url_or_query": str},
    )
    async def analyze_104_job(args: dict[str, Any]) -> dict[str, Any]:
        result = await analyze_104_job_impl(args["url_or_query"])
        body = result.get("webpage_content") or f"(no page content) query: {result['query']}"
        return {"content": [{"type": "text", "text": body}]}

    return create_sdk_mcp_server(
        "job_analysis", version="1.0.0", tools=[analyze_104_job]
    )


def build_websearch_server():
    @tool(
        "web_search",
        "搜尋網際網路，回傳排名的網頁結果（標題、網址、摘要）。需要找來源、頁面或網址時使用。",
        {"query": str, "count": int, "freshness": str, "country": str, "search_lang": str},
    )
    async def web_search(args: dict[str, Any]) -> dict[str, Any]:
        result = await web_search_impl(
            query=args["query"],
            search_type="web",
            count=int(args.get("count", 8)),
            freshness=args.get("freshness"),
            country=args.get("country"),
            search_lang=args.get("search_lang"),
        )
        return {"content": [{"type": "text", "text": result["formatted"]}]}

    @tool(
        "web_search_context",
        "搜尋網際網路並回傳從多個來源擷取、適合回答事實性問題的內容（含來源網址，可引用）。需要閱讀網頁內容來回答問題時優先使用此工具。",
        {
            "query": str,
            "count": int,
            "max_tokens": int,
            "freshness": str,
            "country": str,
            "search_lang": str,
        },
    )
    async def web_search_context(args: dict[str, Any]) -> dict[str, Any]:
        result = await web_search_impl(
            query=args["query"],
            search_type="context",
            count=int(args.get("count", 5)),
            max_tokens=int(args.get("max_tokens", 4096)),
            freshness=args.get("freshness"),
            country=args.get("country"),
            search_lang=args.get("search_lang"),
        )
        return {"content": [{"type": "text", "text": result["formatted"]}]}

    @tool(
        "image_search",
        "搜尋網際網路上既有的圖片，回傳圖片網址與來源。當使用者要求尋找、顯示、觀看圖片或視覺參考時使用。",
        {
            "query": str,
            "count": int,
            "country": str,
            "search_lang": str,
        },
    )
    async def image_search(args: dict[str, Any]) -> dict[str, Any]:
        result = await web_search_impl(
            query=args["query"],
            search_type="image",
            count=int(args.get("count", 8)),
            country=args.get("country"),
            search_lang=args.get("search_lang"),
        )
        return {"content": [{"type": "text", "text": result["formatted"]}]}

    return create_sdk_mcp_server(
        "websearch",
        version="1.0.0",
        tools=[web_search, web_search_context, image_search],
    )


def build_discord_server(toolset: DiscordToolset):
    @tool(
        "fetch_channel_history",
        "從 Discord 頻道取最近 N 則訊息，oldest → newest 排序。",
        {"channel_id": str, "limit": int},
    )
    async def fetch_channel_history(args: dict[str, Any]) -> dict[str, Any]:
        msgs = await toolset.fetch_channel_history(
            channel_id=int(args["channel_id"]),
            limit=int(args.get("limit", 20)),
        )
        lines = [f"{m['created_at']} {m['author']}: {m['content']}" for m in msgs]
        return {"content": [{"type": "text", "text": "\n".join(lines) or "(empty)"}]}

    @tool(
        "send_embed",
        "在 Discord 頻道送一則 embed。",
        {
            "channel_id": str,
            "title": str,
            "description": str,
            "fields": list,
            "color": int,
        },
    )
    async def send_embed(args: dict[str, Any]) -> dict[str, Any]:
        ok = await toolset.send_embed(
            channel_id=int(args["channel_id"]),
            title=args["title"],
            description=args.get("description"),
            fields=args.get("fields"),
            color=int(args.get("color", 0xEE82EE)),
        )
        return {"content": [{"type": "text", "text": "sent" if ok else "failed"}]}

    @tool(
        "react_to_message",
        "對某則 Discord 訊息加 emoji reaction。",
        {"channel_id": str, "message_id": str, "emoji": str},
    )
    async def react_to_message(args: dict[str, Any]) -> dict[str, Any]:
        ok = await toolset.react_to_message(
            channel_id=int(args["channel_id"]),
            message_id=int(args["message_id"]),
            emoji=args["emoji"],
        )
        return {"content": [{"type": "text", "text": "reacted" if ok else "failed"}]}

    @tool(
        "get_member_info",
        "查詢 Discord 使用者（可選指定 guild 以取得 member 資訊）。",
        {"user_id": str, "guild_id": str},
    )
    async def get_member_info(args: dict[str, Any]) -> dict[str, Any]:
        info = await toolset.get_member_info(
            user_id=int(args["user_id"]),
            guild_id=int(args["guild_id"]) if args.get("guild_id") else None,
        )
        return {"content": [{"type": "text", "text": str(info) if info else "not found"}]}

    return create_sdk_mcp_server(
        "discord",
        version="1.0.0",
        tools=[
            fetch_channel_history,
            send_embed,
            react_to_message,
            get_member_info,
        ],
    )
