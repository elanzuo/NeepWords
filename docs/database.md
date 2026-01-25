# 数据库设计（SQLite）

输出文件：`output/words.sqlite3`  
主要表：`words`

## 表结构

| 字段 | 类型 | 约束/索引 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PRIMARY KEY | 内部自增主键 |
| `word` | TEXT | NOT NULL | 展开后的单词变体（保留原始大小写/格式） |
| `norm` | TEXT | NOT NULL UNIQUE | 规范化单词（小写 + 合并空白），用于去重与检索 |
| `source` | TEXT |  | 来源标记（例如 `26_exam_outline_pdf-147-R-17-stor(e)y`） |
| `ipa` | TEXT |  | 国际音标（可空） |
| `frequency` | INTEGER | NOT NULL DEFAULT 1 | 单词在抽取过程中的累计出现次数 |
| `created_at` | TEXT | NOT NULL DEFAULT (strftime(...)) | 记录创建时间（UTC ISO） |
| `updated_at` | TEXT | NOT NULL DEFAULT (strftime(...)) | 记录更新时间（UTC ISO） |

## 字段含义说明

- `id`：数据库内部主键，自增。
- `word`：OCR 清洗并展开后的单词变体，保留原始格式以便人工核对。
- `norm`：对 `word` 做规范化（合并多空格、转小写），作为唯一约束与检索主键。
- `source`：可追溯来源标签，格式建议为 `pdfName-page-column-line-word`。
- `ipa`：可选国际音标；后续可补充。
- `frequency`：同一个 `norm` 重复出现时自动累加。
- `created_at` / `updated_at`：使用 SQLite 默认时间戳，UTC ISO 格式。

## 示例数据

| id | word | norm | source | ipa | frequency | created_at | updated_at |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `story` | `story` | `26_exam_outline_pdf-147-R-17-stor(e)y` | `ˈstɔːri` | 2 | `2026-01-25T10:12:30.123Z` | `2026-01-25T10:12:30.123Z` |
| 2 | `storey` | `storey` | `26_exam_outline_pdf-147-R-17-stor(e)y` |  | 1 | `2026-01-25T10:12:30.123Z` | `2026-01-25T10:12:30.123Z` |
| 3 | `gaol` | `gaol` | `26_exam_outline_pdf-148-L-3-gaol / jail` |  | 1 | `2026-01-25T10:12:31.456Z` | `2026-01-25T10:12:31.456Z` |
| 4 | `jail` | `jail` | `26_exam_outline_pdf-148-L-3-gaol / jail` |  | 1 | `2026-01-25T10:12:31.456Z` | `2026-01-25T10:12:31.456Z` |

## 展开规则说明

- 斜杠变体：`word1 / word2` 拆为两条记录 `word1` 与 `word2`，共享同一条 `source`。
- 括号变体：`stor(e)y` 展开为 `story` 与 `storey`，共享同一条 `source`。
- 组合场景：`colou(r) / color` 展开为 `colour` 与 `color`。
- `source` 仍以“清洗后的原始行”生成，以便回溯原始 OCR 行。

## 备注

- 目前以 `norm` 作为唯一键；若将来需要记录每次出现，可新增 `occurrences` 表。
