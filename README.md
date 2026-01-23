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

## CLI 参数

- `--pdf`：输入 PDF 路径（必填）
- `--start-page`：起始页码，1-based（必填）
- `--end-page`：结束页码，1-based（必填）
- `--output-dir`：输出目录（必填）
- `--debug-dir`：调试输出目录（可选，保存裁剪/分栏等中间图像）

## 技术栈

- PDF 渲染：pypdfium2
- 图像处理：PIL (Pillow)
- OCR 引擎：ocrmac (Apple Vision)
