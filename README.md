# NeepWordExtractor

一个用于从扫描版考研英语（NEEP）大纲 PDF 指定页码范围中提取词汇的 Python OCR 工具，针对 macOS Apple Silicon 优化。

## 目录

- [提取词汇（主命令）](#提取词汇主命令)
- [添加词汇（add-words）](#添加词汇add-words)
- [导出词表（export-csv）](#导出词表export-csv)
- [原理与流程](#原理与流程)
- [技术栈](#技术栈)

## 提取词汇（主命令）

```bash
uv sync
uv run neepwordextractor --pdf resources/pdfs/26考研英语一考试大纲.pdf \
  --start-page 45 \
  --end-page 165 \
  --spellcheck-language en_GB \
  --spellcheck-language en \
  --split-offset -0.1
```

说明：`uv sync` 会安装项目命令入口（`neepwordextractor`）。

CLI 输入的页码为 1-based（从 1 开始）。

拼写检查示例：

```bash
# 关闭 Cocoa 拼写检查
uv run neepwordextractor --pdf resources/pdfs/26考研英语一考试大纲.pdf \
  --start-page 146 \
  --end-page 147 \
  --no-spellcheck

# 拼写检查未通过也写入数据库
uv run neepwordextractor --pdf resources/pdfs/26考研英语一考试大纲.pdf \
  --start-page 146 \
  --end-page 147 \
  --spellcheck-rejected db
```

调试输出：

```bash
uv run neepwordextractor --pdf resources/pdfs/26考研英语一考试大纲.pdf \
  --start-page 45 \
  --end-page 45 \
  --spellcheck-language en_GB \
  --spellcheck-language en \
  --split-offset -0.1  \
  --debug-dir debug
```

参数（主命令）：

- `--pdf`：输入 PDF 路径（必填）
- `--start-page`：起始页码，1-based（必填）
- `--end-page`：结束页码，1-based（必填）
- `--output-dir`：输出目录（默认 `output`）
- `--debug-dir`：调试输出目录（可选，保存裁剪/分栏等中间图像），例如`--debug-dir debug`
- `--spellcheck` / `--no-spellcheck`：是否启用 Cocoa 拼写检查（默认启用）
- `--spellcheck-rejected`：拼写检查未通过单词的去向（`csv` 或 `db`，默认 `csv`）
- `--spellcheck-language`：拼写检查语言（可重复，默认 `en`）
- `--split-offset`（`--split-offse`）：双栏分割偏移（默认 `0.0`，相对页宽的比例）

## 添加词汇（add-words）

用于复核 rejected_words.csv 后手动入库：

```bash
uv run neepwordextractor add-words \
  --entry "endeavour:26考研英语一考试大纲-81-L-2-endeavour" \
  --entry "favourite:26考研英语一考试大纲-86-L-8-favourite" \
  --entry "humourous:26考研英语一考试大纲-97-R-4-humo(u)rous" \
  --entry "policewoman:26考研英语一考试大纲-125-L-3-policeman / policewoman"
```

说明：`--entry` 支持 `word[:source]`，source 可省略。

参数（add-words）：

- `--entry`：词条 `word[:source]`（可重复）
- `--db-path`：指定 `words.sqlite3` 路径（默认 `output/words.sqlite3`）

## 导出词表（export-csv）

```bash
uv run neepwordextractor export-csv --csv-path words/2026-01-26.csv --columns word --db-path output/words.sqlite3
uv run neepwordextractor export-csv --csv-path words/2026-01-26-source.csv --columns word,source --db-path output/words.sqlite3
```

说明：默认导出路径为 `words/YYYY-MM-DD.csv`，默认导出列为 `word,source`。

参数（export-csv）：

- `--db-path`：指定导出的 `words.sqlite3` 路径（默认 `output/words.sqlite3`）
- `--csv-path`：指定导出的 CSV 路径（默认 `words/YYYY-MM-DD.csv`）
- `--columns`：指定导出列（默认 `word,source`，逗号分隔）

## 原理与流程

整体流程基于“渲染 -> 图像处理 -> OCR -> 规范化/扩展 -> 拼写检查 -> 入库/导出”的流水线：

1. PDF 页面渲染为高分辨率图像（pypdfium2）。
2. 图像裁剪去除页眉/页脚，并进行对比度/二值化等增强处理（PIL）。
3. 对双栏页面进行左右分栏，逐栏调用 OCR（ocrmac / Apple Vision）。
4. OCR 文本清洗与规范化，词形扩展（例如大小写/标点处理等）。
5. Cocoa 拼写检查：通过的词进入数据库；未通过的词写入 `rejected_words.csv` 或按配置写入数据库。
6. 写入 `words.sqlite3`，按 `norm` 去重并累计 `frequency`。

## 技术栈

- PDF 渲染：pypdfium2
- 图像处理：PIL (Pillow)
- OCR 引擎：ocrmac (Apple Vision)
