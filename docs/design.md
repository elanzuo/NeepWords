# 设计方案：考研英语一考试大纲 PDF 单词提取

## 目标
- 输入：扫描版 PDF（《考研英语一考试大纲.pdf》），指定页码范围
- 输出：约 100+ 页、约 5500 词的结构化单词列表
- 平台：macOS（Apple Silicon）

## 技术栈与职责
- PDF 渲染：`pypdfium2`（高保真扫描页渲染）
- 图像处理：`PIL`（裁剪页眉/页脚、分栏）
- OCR 引擎：`ocrmac`（Apple Vision）

## 流程概览
1) PDF -> 图像（逐页渲染）
2) 图像预处理（裁剪 + 分栏 + 可选增强）
3) OCR（左右列分别识别）
4) 文本清洗（过滤噪声、标准化）
5) 输出与校验（统计、可追溯）
6) 可视化调试（可选，参数驱动）

## 详细步骤
### 1) PDF 渲染（pypdfium2）
- 仅渲染用户指定的页码范围
- 渲染输出为 PIL Image（优先内存流，必要时可落盘用于调试）
- 建议 DPI：300（必要时提升到 350）

### 2) 图像预处理（PIL）
- 页眉/页脚裁剪：按比例裁剪，去除页码、标题等噪声
  - 初始建议：顶部 6–8%，底部 5–7%
  - 抽样 3–5 页微调后固定
- 分栏：按中线将页面切为左右两列
  - 可引入 1–2% 偏移，避免中缝文字被切断
- 可选增强：轻度对比度增强或二值化

### 3) OCR（ocrmac）
- 左列与右列分别执行 OCR
- 保留行级输出，保留页码、列号、行号信息，便于追溯

### 4) 文本清洗与规范化
- 白名单字符：仅保留 `[a-zA-Z\\-()\\/ ]`，剔除页码或中文残留
- 原始格式优先：保留 `gaol / jail` 之类的同义词格式，仅规范空格
- 变体展开：处理 `word1 / word2` 与 `stor(e)y`，生成多条词条
- 连字符处理：检查行尾连字符（Hyphenation），尽量避免跨行误拼
- 多空格合并为单空格
- 过滤噪声行（过短、非字母为主）

### 5) 输出与校验
- 主要输出：`output/words.sqlite3`（表 `words`，含 `word/norm/source/ipa/frequency/created_at/updated_at`）
- 拼写检查：默认启用 macOS Cocoa (`NSSpellChecker`) 过滤
  - 通过检查的单词进入 SQLite
  - 未通过默认写入 `output/rejected_words.csv`（列：`word/reason/source/page/column/line`）
  - 可通过 CLI 关闭检查或选择未通过写入数据库
- 统计信息：总词数、重复词数、每页词数（基于通过检查的词）

### 6) 可视化调试（Visual Debugging）
- CLI 增加 `--debug` 或 `--preview` 参数
- 开启后在 `debug/` 保存中间图像，用于快速校准参数
  - `page_090_original.png`（原始渲染）
  - `page_090_cropped.png`（裁剪框检查）
  - `page_090_split_L.png` / `page_090_split_R.png`（分栏检查）

## 结构建议
```
NeepWordExtractor/
  src/
    neepwordextractor/
      __init__.py
      main.py             # CLI 入口
      core.py             # 流程编排
      pdf_renderer.py     # pypdfium2 渲染
      image_proc.py       # 裁剪/分栏/增强
      ocr_engine.py       # ocrmac 封装
      cleaner.py          # OCR 文本清洗
      output.py           # 输出与统计
  debug/                  # 调试中间图像（建议加入 .gitignore）
  output/                 # 结果输出
  resources/
    考研英语一考试大纲.pdf
```

## 风险与规避
- OCR 错误：提高 DPI 或做轻度图像增强
- 分栏切割误差：中缝偏移或引入留白阈值
- 页眉页脚残留：抽样页校准裁剪比例

## 下一步
- 实现最小可用 CLI：指定页码范围、输出路径
- 增加可视化调试模式：便于确认裁剪/分栏效果
- 逐步完善清洗规则与统计校验
