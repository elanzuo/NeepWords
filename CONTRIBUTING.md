# Contributing to NeepWords

感谢你为 NeepWords 做贡献。

这个项目的目标不是做一个泛用英语词典，而是提供一套可验证、可追溯的本地工具，用来判断某个单词是否属于考研词表，并按特征检索这些单词。请尽量围绕这个目标提交改动。

## 开始之前

- Python 版本要求：`>= 3.13`
- 包管理工具：`uv`
- 默认开发安装：

```bash
uv sync --group dev
```

- 如果你要调试 OCR 或 macOS 拼写检查：

```bash
uv sync --group dev --extra macos
```

## 建议的贡献方向

- 修复词表查询、版本解析、SQLite 读写相关 bug
- 增加更清晰的 CLI / MCP 文档和示例
- 改进 OCR 清洗、分栏、来源追溯、调试输出
- 增加测试覆盖，特别是非 OCR 逻辑
- 改善跨版本查询体验和错误提示

## 不建议的改动方向

- 将项目扩展成通用词典、翻译器或背单词平台
- 在没有充分说明的前提下改变“是否为考研词”的判断标准
- 将未确认授权的 PDF、截图、完整词表数据库直接提交到仓库

## 开发流程

1. Fork 仓库并创建分支。
2. 保持改动范围尽量小，围绕单一问题提交。
3. 为行为变化补测试。
4. 本地跑通检查后再发起 Pull Request。

常用命令：

```bash
uv run neepwords --help
uv run pytest -q
uvx ruff check src tests
uv build
```

## 代码风格

- 使用 4 空格缩进和标准 PEP 8 命名
- 模块尽量保持小而专注
- 优先使用清晰、语义明确的名称
- 没有必要时不要引入复杂抽象
- 新增依赖前请说明理由，尤其是平台绑定依赖

## 测试要求

- 测试框架使用 `pytest`
- 测试文件放在 `tests/`
- 文件名格式使用 `test_<module>_<behavior>.py`
- 优先为纯函数、CLI 参数解析、数据库逻辑、查询逻辑补测试
- OCR 相关测试应避免依赖私有 PDF 或难以复现的本地环境

## 文档要求

如果你的改动影响以下内容，请同步更新文档：

- CLI 参数或默认行为
- MCP tool 行为或返回结构
- 版本解析逻辑
- 数据库 schema 或导出格式
- 平台支持与依赖安装说明

## 数据与版权要求

- 不要提交你无权再分发的原始 PDF
- 不要提交受版权保护的扫描页截图，除非你明确拥有公开权限
- 不要默认把真实提取库当成可公开再分发的示例数据
- 如果 PR 涉及示例库或示例截图，请在说明中交代数据来源与授权状态

## Pull Request 要求

每个 PR 请尽量包含：

- 改动目的
- 用户可见的行为变化
- 测试情况
- 如果涉及 OCR、词表导入或导出，给出最小复现示例

推荐提交信息格式：

```text
type: short summary
```

例如：

```text
feat: add wildcard search pagination
fix: resolve default version precedence
docs: clarify macos-only OCR requirements
```
