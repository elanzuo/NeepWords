import os
import sys
from typing import Any, cast

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# 确保测试可以使用项目根目录下的模块
sys.path.append(os.getcwd())


def _content_text(item: Any) -> str:
    """Extract text content from MCP responses in a type-safe way."""
    if isinstance(item, str):
        return item
    text = getattr(item, "text", None)
    if not isinstance(text, str):
        raise AssertionError("Expected text content in MCP response.")
    return cast(str, text)


@pytest.mark.asyncio
async def test_mcp_server_tools():
    """Test that the MCP server exposes the expected tools and they work."""

    # 定义服务器启动参数
    # 注意：我们直接调用 python 解释器运行模块，确保环境一致
    server_params = StdioServerParameters(
        command=sys.executable,  # 使用当前的 Python 解释器
        args=["-m", "neep_mcp.server"],
        env={
            **os.environ,
            # 显式指定数据库路径，确保测试环境稳定
            "NEEP_WORDS_DB_PATH": "resources/data/words.sqlite3",
        },
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # --- Test 1: List Tools ---
            tools_result = await session.list_tools()
            tool_names = [t.name for t in tools_result.tools]

            assert "lookup_words" in tool_names
            assert "search_words" in tool_names
            assert "get_random_words" in tool_names

            # 验证 Docstring 是否被正确解析为 description
            lookup_tool = next(t for t in tools_result.tools if t.name == "lookup_words")
            assert "Look up multiple words" in (lookup_tool.description or "")
            assert "match" in lookup_tool.inputSchema["properties"]

            # --- Test 2: Call lookup_words ---
            # 测试查找存在的词
            result = await session.call_tool(
                "lookup_words", arguments={"words": ["abandon", "zxqjz_qwerty"]}
            )

            data = _content_text(result.content[0])
            # 这里需要根据实际返回结构解析，FastMCP 返回的是 JSON 字符串还是对象取决于 SDK 版本
            # 但根据 stdio client 的实现，通常 content 是 TextContent 对象
            import json

            response = json.loads(data)

            assert response["ok"] is True
            results = response["data"]["results"]

            # 验证 "abandon" 找到了
            found_abandon = next((r for r in results if r.get("query") == "abandon"), None)
            assert found_abandon is not None
            assert found_abandon["found"] is True

            # 验证 "zxqjz_qwerty" 没找到
            # "zxqjz_qwerty" -> tokens: ["zxqjz", "qwerty"] -> max: "qwerty" (6 chars)
            # "qwerty" 肯定不在考研大纲里
            not_found = next((r for r in results if "zxqjz" in r["input"]), None)
            assert not_found is not None
            # 注意：sanitizer 可能会把 not_a_word_123 清理成 notaword 或者拒绝
            # 如果被 sanitizer 拒绝，found 可能是 False 或者有 error
            if "error" not in not_found:
                assert not_found["found"] is False

            # --- Test 3: Call get_random_words ---
            # Wait for rate limiter (default 0.5s)
            import asyncio

            await asyncio.sleep(0.6)

            random_result = await session.call_tool("get_random_words", arguments={"count": 3})
            random_resp = json.loads(_content_text(random_result.content[0]))
            assert random_resp["ok"] is True
            assert len(random_resp["data"]["results"]) == 3
