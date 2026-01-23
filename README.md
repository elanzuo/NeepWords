# NeepWordExtractor

一个用于从扫描版考研英语（NEEP）大纲 PDF 指定页码范围中提取词汇的 Python OCR 工具，针对 macOS Apple Silicon 优化。

## 快速开始

```bash
uv run python -m neepwordextractor --pdf resources/考研英语一考试大纲.pdf \
  --start-page 1 \
  --end-page 3 \
  --output-dir output \
  --debug-dir debug
```

CLI 输入的页码为 1-based（从 1 开始）。

## 技术栈

- PDF 渲染：pypdfium2
- 图像处理：PIL (Pillow)
- OCR 引擎：ocrmac (Apple Vision)
