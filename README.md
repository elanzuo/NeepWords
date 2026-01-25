# NeepWordExtractor

一个用于从扫描版考研英语（NEEP）大纲 PDF 指定页码范围中提取词汇的 Python OCR 工具，针对 macOS Apple Silicon 优化。

## 快速开始

```bash
uv sync
uv run neepwordextractor --pdf resources/pdfs/26考研英语一考试大纲.pdf \
  --start-page 146 \
  --end-page 147 \
  --output-dir output \
  --debug-dir debug
```

说明：`uv sync` 会安装项目命令入口（`neepwordextractor`）。

CLI 输入的页码为 1-based（从 1 开始）。

拼写检查示例：

```bash
# 关闭 Cocoa 拼写检查
uv run neepwordextractor --pdf resources/pdfs/26考研英语一考试大纲.pdf \
  --start-page 146 \
  --end-page 147 \
  --output-dir output \
  --no-spellcheck

# 拼写检查未通过也写入数据库
uv run neepwordextractor --pdf resources/pdfs/26考研英语一考试大纲.pdf \
  --start-page 146 \
  --end-page 147 \
  --output-dir output \
  --spellcheck-rejected db
```

## CLI 参数

- `--pdf`：输入 PDF 路径（必填）
- `--start-page`：起始页码，1-based（必填）
- `--end-page`：结束页码，1-based（必填）
- `--output-dir`：输出目录（必填）
- `--debug-dir`：调试输出目录（可选，保存裁剪/分栏等中间图像）
- `--spellcheck` / `--no-spellcheck`：是否启用 Cocoa 拼写检查（默认启用）
- `--spellcheck-rejected`：拼写检查未通过单词的去向（`csv` 或 `db`，默认 `csv`）

## 技术栈

- PDF 渲染：pypdfium2
- 图像处理：PIL (Pillow)
- OCR 引擎：ocrmac (Apple Vision)
