# 数据库设计（SQLite）

输出文件：`output/words.sqlite3`

当前采用“单库多版本”设计，同一个 SQLite 可以同时保存 `2026`、`2027` 等多个考研词表版本。

## 表结构

### `vocab_versions`

| 字段 | 类型 | 约束/索引 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PRIMARY KEY | 内部主键 |
| `version_key` | TEXT | NOT NULL UNIQUE | 规范化版本号，如 `2026`、`2027` |
| `label` | TEXT |  | 展示标签，如 `2027考研大纲` |
| `source_pdf` | TEXT |  | 导入来源 PDF 路径 |
| `imported_at` | TEXT | NOT NULL DEFAULT (strftime(...)) | 版本记录创建时间（UTC ISO） |
| `is_default` | INTEGER | NOT NULL DEFAULT 0 | 是否为数据库默认查询版本 |

### `words`

| 字段 | 类型 | 约束/索引 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PRIMARY KEY | 内部主键 |
| `version_id` | INTEGER | NOT NULL, FK -> `vocab_versions.id` | 所属版本 |
| `word` | TEXT | NOT NULL | 规范化后的唯一单词（小写存储） |
| `source` | TEXT |  | 来源标记（例如 `26_exam_outline_pdf-147-R-17-stor(e)y`） |
| `added_at` | TEXT | NOT NULL DEFAULT (strftime(...)) | 首次入库时间（UTC ISO） |

## 约束与索引

- `UNIQUE(version_id, word)`：同一版本内唯一；不同版本允许重复。
- `idx_words_version_word(version_id, word)`：版本内查询主索引。
- `idx_words_word(word)`：跨版本排查或调试辅助索引。

## 查询版本解析优先级

查询入口（skill、MCP、本地 CLI）按以下顺序决定版本：

1. 显式参数，如 `--version 2027` 或 MCP `version="2027"`
2. 环境变量 `NEEP_WORDS_VERSION`
3. 仓库根目录 `neep.toml` 中 `[words].default_version`
4. 数据库中 `vocab_versions.is_default = 1`
5. 数据库只有一个版本时自动选择该版本

若数据库包含多个版本且以上来源都未指定，则返回 `missing_version`。

## 配置文件

可选配置文件：`neep.toml`

```toml
[words]
db_path = "resources/data/words.sqlite3"
default_version = "2027"
```

## 导入规则

- 提取导入和 `add-words` 都必须显式提供 `--version`。
- 版本输入支持 `2027`、`27`、`2027考研`、`27考研`，最终统一规范化为 `2027`。
- 第一次写入一个新库时，首个版本会自动标记为默认版本。

## 旧库迁移

旧单版本库的 `words(word UNIQUE)` 无法自动判断属于哪一年，迁移时必须显式指定：

```bash
uv run python -m word_extractor migrate-db \
  --db-path output/words.sqlite3 \
  --legacy-version 2026
```

或者在首次向旧库导入新版本时一并提供旧版本：

```bash
uv run python -m word_extractor \
  --pdf resources/2027.pdf \
  --start-page 1 \
  --end-page 10 \
  --output-dir output \
  --version 2027 \
  --legacy-version 2026
```

## 版本管理命令

查看数据库中已有版本：

```bash
uv run python -m word_extractor list-versions --db-path output/words.sqlite3
```

切换数据库默认版本：

```bash
uv run python -m word_extractor set-default-version \
  --db-path output/words.sqlite3 \
  --version 2027
```

## 示例数据

### `vocab_versions`

| id | version_key | label | is_default |
| --- | --- | --- | --- |
| 1 | `2026` | `2026考研大纲` | 1 |
| 2 | `2027` | `2027考研大纲` | 0 |

### `words`

| id | version_id | word | source | added_at |
| --- | --- | --- | --- | --- |
| 1 | 1 | `story` | `26_exam_outline_pdf-147-R-17-stor(e)y` | `2026-01-25T10:12:30.123Z` |
| 2 | 1 | `storey` | `26_exam_outline_pdf-147-R-17-stor(e)y` | `2026-01-25T10:12:30.123Z` |
| 3 | 2 | `story` | `27_exam_outline_pdf-148-L-2-story` | `2026-08-01T08:00:00.000Z` |

## 展开规则说明

- 斜杠变体：`word1 / word2` 拆为两条记录，版本相同，`source` 相同。
- 括号变体：`stor(e)y` 展开为 `story` 与 `storey`，版本相同，`source` 相同。
- `source` 仍以“清洗后的原始行”生成，以便回溯原始 OCR 行。
