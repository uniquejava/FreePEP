# 01: 新概念英语 1–4 册词源索引

**项目票号（会话标题用）：** `#02`  
**What to build:** 为《新概念英语》第 1、2、3、4 册建立单词来源倒排索引。当前版本只标记出现的册数，格式与现行人教初高中索引一致，供 EggplantDict 等查词打标。

**Status:** resolved

**Blocked by:** （无；格式先例见 english-vocab-ocr `#01`）

## 索引格式（与人教同一 schema）

产出路径：`data/vocab/nce-vocab-index.min.json`  
（与 PEP 分文件，但 **格式相同**：`v` / `books` / `w`，hit 槽位一致，Swift 共用解码器。版本号共用 `INDEX_VERSION = 1`。）

```json
{
  "v": 1,
  "books": {
    "nce-1": "新概念英语第一册",
    "nce-2": "新概念英语第二册"
  },
  "w": {
    "private": [["nce-2", "", ""]]
  }
}
```

| 字段 | 含义 |
|------|------|
| `v` | **`1`**（与人教相同；破坏性变更前不升） |
| `books` | `book_id` → 显示名 |
| `w` | 小写 lemma → 出现列表 |
| 每条 hit | 当前册级版为 `[book_id, "", ""]`：保留 `v:1` 三段形状，第二段无课次，第三段无教材释义 |
| 一词多册 | **每册一条 hit**；同册重复词只保留一次 |
| 词性 | **不进索引**；仅 `_work` CSV 的 `pos` 列供校对 |

`book_id` 约定：`nce-1` / `nce-2` / `nce-3` / `nce-4`。

## Lesson vs Unit

- 新概念正文按 **Lesson** 编号（二册常见 1–96，三册 1–60，四册 1–48；以实际词表源为准）。
- 当前册级版不查 Lesson；第二段为空，词典侧只显示册名。
- 若以后恢复课次索引，再以有来源的 Lesson 号填第二段。

## 范围

- 册：新概念英语经典新版 **1、2、3、4**。
- 词表：每册 Excel 的“单词”列；只判断词条在哪一册，不做 Lesson 或教材释义对齐。
- 源：[lilinji/English](https://github.com/lilinji/English) 的四份新版 Excel，本机路径 `~/code/English/8.新概念英语/`；生成脚本允许指定目录。

## 验收

- [x] 二册课次试点曾产出 `nce-vocab-index.min.json`，`v:1`，hit=`[book_id, lesson, zh]`（历史版本）
- [x] 当前册级版覆盖 1–4 册，每册均有 `books` 条目与词条
- [x] 每词每册最多一条 hit，且 hit=`[book_id, "", ""]`
- [x] README 写明复跑命令、Excel 来源、册级精度与许可
- [x] 抽核四册首尾词与跨册词条

## 非目标

- 不在本票改 EggplantDict 打标逻辑（另票接入 `nce-*` →「新概念英语2」等 Catalog Tag）
- 不强制与 PEP 索引合并为单一文件
- **词性不进索引**（不嵌进 `zh`，不另开 hit 槽位）

## Comments

- 与人教同一 schema：`v:1` + hit=`[book, unit|lesson, (page?), zh]`（`vocab_ocr.shared.build_index`）。
- 会话标题建议：`#02 新概念二册词源试点`。
- **源定点（新版）**：`/Users/cyper/Pdf/nce-new/`（自 [tangx/New-Concept-English](https://github.com/tangx/New-Concept-English)）；勿用本地残本「刘晓华」四册。
- **试点流水线（绕开模糊 PDF 全书 OCR）**：`python3 -m vocab_ocr.nce.pilot_nce2_from_excel`
  - Excel：`~/code/English/8.新概念英语/新概念英语第二册（新版）.xlsx`
  - 课次表：搜狐二册按 Lesson 词表（缓存 `_work/nce-2/sohu-lesson-vocab.txt`）
  - `_work`：`excel.csv` / `excel-with-lesson.csv`（含 `pos`）/ `lesson-vocab.csv`（含 `pos`）
  - 产出：`data/vocab/nce-vocab-index.min.json`
- **词性**：解析进 `_work` CSV 的 `pos` 列供校对；**不写进索引 hit**。若词典以后要展示词性，另开票再定 schema（升 `v`）。
- 例：`private` → nce-2 Lesson 1「私人的」；`until` → Lesson 2；`spectacle` → Lesson 96。
- 2026-10-08：曾整票取消；同日重启仅 nce-2 试点；人教索引亦改回 `v:1` 与 NCE 对齐。
- 2026-10-08：已拷贝 `nce-vocab-index.min.json` → EggplantDict `Resources/`（并入 Xcode Resources）；词典打标接 `nce-*` 仍属 EggplantDict 另票，非本票。
- 2026-10-08：脚本新增 `--xlsx`、`--lesson-vocab`，README 写明四列 Excel 和课次词表的来源及本机副本用法。
- 2026-10-08：用户将范围扩到经典版 1–4 册，并改为先做册级索引；不再为第一版逐词对齐 Lesson。四份 Excel 分别有 908 / 862 / 1062 / 793 行，来源为 [lilinji/English](https://github.com/lilinji/English)。二册课次试点脚本保留作历史工具，正式 NCE 索引改由册级生成器重建。

## Answer

运行 `python3 -m vocab_ocr.nce.build_book_index` 可直接由四份 Excel 重建册级索引。当前索引包含 3357 个不同词头；四册各有 867 / 840 / 1050 / 784 个去重词头，178 个词头出现在多册。抽核 `excuse`、`private`、`puma`、`fossil man` 分别命中第一至四册，`abroad` 同时命中第一和第二册。Lesson 与教材原文释义尚无可靠来源，因此两个槽位留空。
