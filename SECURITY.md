# Security Policy

## Supported Versions

当前默认只对最新提交和最新发布版本提供安全修复支持。

在项目仍处于早期阶段时，历史版本通常不会单独回补安全更新。

## Reporting a Vulnerability

如果你发现了安全问题，请不要公开提交 issue、PR 或 discussion 细节。

请优先使用私下渠道联系维护者，例如：

- GitHub private vulnerability reporting（如果仓库已启用）
- 维护者在 GitHub 个人资料或仓库资料中公开的私下联系方式

报告时请尽量提供：

- 问题描述
- 影响范围
- 复现步骤或最小 PoC
- 受影响的系统、Python 版本、运行方式
- 你认为的修复建议（如果有）

## What to Expect

维护者会尽量：

- 确认是否能够复现
- 评估影响范围和修复优先级
- 在修复后公开必要信息

但由于这是个人维护的开源项目，响应时间不保证为固定 SLA。

## Security Scope

对本项目而言，更值得优先报告的安全问题包括：

- MCP server 或本地 CLI 导致的非预期文件访问
- SQLite 路径解析、配置解析或输入清理导致的安全边界问题
- 依赖或打包配置引入的明显供应链风险

以下内容通常不按安全漏洞处理：

- 词表内容不完整、OCR 识别错误、拼写误判
- 普通功能 bug
- 没有明确安全影响的文档问题
