### 1. 首选推荐：利用 macOS 原生拼写检查 (NSSpellChecker)

macOS 系统内置了一套非常成熟的拼写检查引擎（就是你在 Pages 或备忘录里写错单词会弹红线的那个）。通过 `PyObjC` 库，你可以直接在 Python 中调用这个系统级 API。

* **优点**：
* **零内存占用**：直接调用系统服务，不额外加载巨大的词典文件。
* **极速**：针对 M 系列芯片优化，处理 5500 个单词仅需几秒。
* **权威**：系统自带词典更新频繁，对英美拼写变体支持极好。


* **安装**：`uv add pyobjc-framework-Cocoa`
* **代码示例**：
```python
from Cocoa import NSSpellChecker

def check_word_on_mac(word):
    checker = NSSpellChecker.sharedSpellChecker()
    # 检查单词在美式英语词典中是否存在
    range_result = checker.checkSpellingOfString_language_(word, "en_US")
    # 如果返回的范围长度为 0，说明单词是正确的
    return range_result[0] == 0

print(check_word_on_mac("spokesperson")) # True
print(check_word_on_mac("spokesperrson")) # False

```



---

### 2. 性能之王：SymSpell (针对 OCR 纠错优化)

OCR 提取经常会出现“编辑距离”较小的错误（如 `m` 误识别为 `rn`）。**SymSpell** 是目前性能最强的模糊匹配算法，在 M4 芯片上跑 5500 个词几乎是瞬发完成。

* **优点**：
* **纠错能力强**：它能根据你提供的词库，自动计算出最接近的正确单词。
* **精准适配考研**：你可以直接把那 5500 个单词作为“核心词库”喂给它，这样它只会把 OCR 错误修正为**考研大纲内的单词**。


* **安装**：`uv add symspellpy`

---


### 3. pyspellchecker

  这是目前最轻量且易于集成的纯 Python 方案。

   * 优点：
       * 纯 Python 实现：没有任何外部 C 语言库依赖（No binary dependencies），安装非常简单，完美兼容 uv 和 macOS。
       * 使用简单：几行代码即可判断单词是否在字典中。
       * 支持纠错：如果你愿意，它甚至可以给出“修正建议”（比如把 OCR 错误的 abandonn 修正为 abandon）。
   * 缺点：
       * 它的词库基于 Peter Norvig 的词频统计，虽然覆盖了绝大多数常用词，但对于极度生僻的词可能会误判（不过考研大纲词汇通常都在其覆盖范围内）。
   * 安装：uv add pyspellchecker
