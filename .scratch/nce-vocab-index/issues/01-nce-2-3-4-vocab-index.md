# 01: 新概念英语 2–4 册词源索引

**项目票号（会话标题用）：** `#02`  
**What to build:** 为《新概念英语》第 2、3、4 册建立单词来源倒排索引，格式与现行人教初高中索引一致，供 EggplantDict 等查词打标。

**Status:** in-progress

**Blocked by:** （无；格式先例见 english-vocab-ocr `#01`）

## 索引格式（与人教同一 schema）

产出路径：`data/vocab/nce-vocab-index.min.json`  
（与 PEP 分文件，但 **格式相同**：`v` / `books` / `w`，hit 槽位一致，Swift 共用解码器。版本号共用 `INDEX_VERSION = 1`。）

```json
{
  "v": 1,
  "books": {
    "nce-2": "新概念英语第二册"
  },
  "w": {
    "private": [["nce-2", "1", "私人的"]]
  }
}
```

| 字段 | 含义 |
|------|------|
| `v` | **`1`**（与人教相同；破坏性变更前不升） |
| `books` | `book_id` → 显示名 |
| `w` | 小写 lemma → 出现列表 |
| 每条 hit | `[book_id, lesson, zh]`；有页码时 `[book_id, lesson, page, zh]`（第二段占 PEP 的 unit 槽） |
| 一词多课 | **多条 hit**，各带该课释义 |
| 词性 | **不进索引**；仅 `_work` CSV 的 `pos` 列供校对 |

`book_id` 约定：`nce-2` / `nce-3` / `nce-4`。

## Lesson vs Unit

- 新概念正文按 **Lesson** 编号（二册常见 1–96，三册 1–60，四册 1–48；以实际词表源为准）。
- **优先写 Lesson 号**到 hit 的第二段（占用与 PEP `unit` 相同的槽位；词典侧可显示为 `Lesson 24`）。
- 仅当源数据只有 Unit、没有 Lesson 时才退回 Unit；有 Lesson 时不要用 Unit 代替。

## 范围

- 册：新概念英语 **2、3、4**（不含 1，除非后续另开票）
- 词表：各册单词表 / 课次词汇（与课本 lesson 可对齐即可）
- 源：开干前在本机定点（PDF 附录 OCR，或已有结构化表如社区 xlsx）；选定后写进 Comments

## 验收

- [x] 产出 `nce-vocab-index.min.json`（当前仅 `nce-2`），`v: 1`，hit=`[book_id, lesson, zh]`
- [ ] 2 / 3 / 4 三册均有 `books` 条目与词条（现阶段只做二册试点）
- [x] hit 第二段为 **lesson** 号（抽样：private→1，postcard→3，spectacle→96）
- [x] README 或 `vocab_ocr` 旁注：如何复跑 / 源路径
- [x] 示例查询写入 Comments

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
