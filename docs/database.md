# 数据库设计（SQLite）

输出文件：`output/words.sqlite3`  
主要表：`words`

## 表结构

| 字段 | 类型 | 约束/索引 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PRIMARY KEY | 内部自增主键 |
| `word` | TEXT | NOT NULL UNIQUE | 规范化后的唯一单词（小写存储） |
| `source` | TEXT |  | 来源标记（例如 `26_exam_outline_pdf-147-R-17-stor(e)y`） |
| `added_at` | TEXT | NOT NULL DEFAULT (strftime(...)) | 首次入库时间（UTC ISO） |

## 字段含义说明

- `id`：数据库内部主键，自增。
- `word`：OCR 清洗并展开后再统一小写的单词，作为唯一约束与检索主键。
- `source`：可追溯来源标签，格式建议为 `pdfName-page-column-line-word`。
- `added_at`：首次入库时间，使用 SQLite 默认时间戳，UTC ISO 格式。

## 示例数据

| id | word | source | added_at |
| --- | --- | --- | --- |
| 1 | `story` | `26_exam_outline_pdf-147-R-17-stor(e)y` | `2026-01-25T10:12:30.123Z` |
| 2 | `storey` | `26_exam_outline_pdf-147-R-17-stor(e)y` | `2026-01-25T10:12:30.123Z` |
| 3 | `gaol` | `26_exam_outline_pdf-148-L-3-gaol / jail` | `2026-01-25T10:12:31.456Z` |
| 4 | `jail` | `26_exam_outline_pdf-148-L-3-gaol / jail` | `2026-01-25T10:12:31.456Z` |

## 展开规则说明

- 斜杠变体：`word1 / word2` 拆为两条记录 `word1` 与 `word2`，共享同一条 `source`。
- 括号变体：`stor(e)y` 展开为 `story` 与 `storey`，共享同一条 `source`。
- 组合场景：`colou(r) / color` 展开为 `colour` 与 `color`。
- `source` 仍以“清洗后的原始行”生成，以便回溯原始 OCR 行。

## 备注

- 目前以 `word` 作为唯一键；若将来需要记录每次出现，可新增 `occurrences` 表。
