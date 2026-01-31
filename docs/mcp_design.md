# NeepWordExtractor MCP Server 设计文档（建议版）

> 基于 `docs/mcp_design.md`，补充“只读边界、安全约束、输入清理、输出统一结构”等关键设计，作为合并后建议版本。

## 1. 概述
本设计旨在为 `NeepWordExtractor` 项目实现一个 Model Context Protocol (MCP) 服务器。
该服务器将允许 AI 助手（如 Claude Desktop, Cursor 等）直接访问本地的 `resources/data/words.sqlite3` 数据库。
通过此接口，AI 可以获取准确的考研大纲词汇、音标、词频及来源信息，从而生成准确的考研辅导内容，避免因模型训练数据偏差导致的“幻觉”。

## 2. 核心架构

- **语言**: Python (>= 3.13)
- **依赖库**: `mcp` (官方 Python SDK)
- **数据源**: `resources/data/words.sqlite3` (SQLite 数据库，可配置路径)
- **通信协议**: Stdio (标准输入输出)，适用于本地运行
- **代码位置**: `src/neep_mcp/` (作为独立模块或子包)
- **读写边界**: **只读访问**（不对数据库进行更新/删除）

## 3. 功能设计

### 3.1 Tools (工具)
工具是 MCP 的核心，允许 AI 主动查询数据库。

#### A. `lookup_words`
* **描述**: 批量精确查询多个单词是否在考研大纲中，并返回各自的详细信息（音标、词频、出现位置）。
* **参数**:
  * `words` (string[], required): 需要查询的单词列表。
  * `match` (string, optional): `word` | `norm` | `auto`，默认 `auto`。
* **返回**: 逐词结果列表（每项包含 `word`、`found`、以及元数据或错误码）。
* **场景**: 用户问“这些词 ['ambiguous', 'derive', 'inevitable'] 在考研大纲里吗？它们的音标是什么？”

#### B. `search_words`
* **描述**: 模糊搜索单词。支持前缀匹配或包含匹配。
* **参数**:
  * `query` (string, required): 搜索关键词。
  * `mode` (string, optional): `prefix` | `contains` | `fuzzy`，默认 `prefix`。
  * `limit` (integer, optional): 返回结果数量限制，默认 10，最大 200。
  * `offset` (integer, optional): 默认 0。
* **返回**: 匹配的单词列表。
* **场景**: 用户问“考研大纲里有哪些以 'trans' 开头的单词？”

#### C. `get_random_words`
* **描述**: 随机获取考研单词。可用于生成测验或每日单词。
* **参数**:
  * `count` (integer, optional): 数量，默认 5，最大 50。
  * `min_frequency` (integer, optional): 最小词频（过滤掉生僻词）。
* **返回**: 单词列表。
* **场景**: 用户说“考我 5 个考研高频词。”

### 3.2 Resources (资源)
资源允许 AI 读取静态数据上下文。虽然主要通过 Tool 查询，但暴露部分统计信息很有用。

* `neep://stats/summary`: 返回数据库的统计信息（总词汇量、最近更新时间、如存在则返回 rejected 相关统计）。
* `neep://stats/schema`: 返回 `words` 表字段与说明（便于 AI 理解数据含义）。

### 3.3 Prompts (提示词)
预设的 Prompt 模板，帮助用户快速启动特定任务。

* **Prompt 名称**: `neep_quiz`
* **描述**: 基于考研大纲生成词汇测验。
* **逻辑**: 调用 `get_random_words` 获取单词，然后要求 AI 生成填空题或同义词辨析。

## 4. 数据库交互 (Schema 参考)
基于 `words` 表结构：

- `word`: 单词拼写
- `norm`: 规范化词形（如有）
- `ipa`: 音标（如有）
- `frequency`: 词频 (如果有)
- `source`: 来源页面/文件
- `created_at`: 收录时间

## 5. 安全与准确性约束

- **只读边界**: 所有查询使用只读连接，禁止 UPDATE/DELETE/INSERT。
- **信息边界**: 只返回数据库中可验证字段，不扩展词义、例句、同义词等未存储内容。
- **证据引用**: 模型输出需引用 MCP 返回字段作为证据（如 `source`、`frequency`、`ipa`）。
- **最小字段集**: 工具返回至少包含 `word` / `norm` / `source` / `ipa` / `frequency`（若字段存在）。
- **“是否考研词汇”的判断标准**: 以 `words` 表是否包含该词为准。
- **速率限制**: 每次会话限制工具调用频率（例如每秒不超过 2 次）。
- **结果上限**: `limit` 默认小、最大限制（如 200），避免大量输出。

## 6. 输入清理规则

- 统一小写；移除前后空白。
- 去除标点与非字母字符，仅保留英文字母与连字符（可配置）。
- 超长字符串直接拒绝（如长度 > 64）。
- 如果输入包含中英文混杂，提取英文词串进行查询。

## 7. 输出结构统一规范

所有 Tool 返回统一 JSON 结构：

```
{
  "ok": true,
  "error": null,
  "data": { ... },
  "warnings": []
}
```

错误示例：

```
{
  "ok": false,
  "error": "word_not_found",
  "data": null,
  "warnings": []
}
```

## 8. 开发计划

1. **环境配置**:
   - 在 `pyproject.toml` 中添加 `mcp` 依赖。
   - 创建 `src/neep_mcp/__init__.py` 和 `src/neep_mcp/server.py`。

2. **实现服务**:
   - 编写 SQLite 连接管理类（只读模式）。
   - 使用 `@mcp.server.tool()` 装饰器实现上述工具逻辑。

3. **配置与运行**:
   - 配置 `uv` 运行脚本。
   - 在 Claude Desktop 配置文件中添加 server 配置。

## 9. 示例配置 (claude_desktop_config.json)

```json
{
  "mcpServers": {
    "neep-words": {
      "command": "uv",
      "args": [
        "run",
        "python",
        "-m",
        "neep_mcp.server"
      ],
      "cwd": "/path/to/NeepWordExtractor"
    }
  }
}
```

## 10. MCP SuperAssistant 连接说明

如果通过 MCP SuperAssistant 在 ChatGPT 等平台调用本 MCP 服务，请按以下流程配置。citeturn3search0

### 10.1 config.json (mcpServers)

`config.json` 结构与 Claude Desktop 的 `mcpServers` 一致，可直接复用。citeturn3search0

```json
{
  "mcpServers": {
    "neep-words": {
      "command": "uv",
      "args": [
        "run",
        "python",
        "-m",
        "neep_mcp.server"
      ],
      "cwd": "/path/to/NeepWordExtractor"
    }
  }
}
```

### 10.2 启动本地代理

使用 MCP SuperAssistant Proxy 启动本地代理（默认端口 `3006`），并选择输出传输类型：citeturn3search0

```bash
npx -y @srbhptl39/mcp-superassistant-proxy@latest --config ./config.json --outputTransport sse
```

可选：

```bash
npx -y @srbhptl39/mcp-superassistant-proxy --config ./config.json --outputTransport streamableHttp
```

```bash
npx -y @srbhptl39/mcp-superassistant-proxy --config ./config.json --outputTransport ws
```

### 10.3 在 SuperAssistant 侧连接

在 MCP SuperAssistant 侧输入本地代理 URL（取决于 `--outputTransport`）：citeturn3search0

* SSE: `http://localhost:3006/sse`
* Streamable HTTP: `http://localhost:3006/mcp`
* WebSocket: `ws://localhost:3006/message`

### 10.4 MCP 指令提示

在对话中插入 MCP SuperAssistant 的 instructions prompt，确保模型能正确生成工具调用格式。citeturn3search0
