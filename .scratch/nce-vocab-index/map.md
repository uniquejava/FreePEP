# nce-vocab-index（项目票 #02）— **in-progress**（仅 nce-2 试点）

先做新概念二册：Excel → CSV，用公开课次词表补 Lesson。与人教共用同一索引 schema。

## Decisions so far

- 2026-10-08：曾整票取消并删除 `vocab_ocr/nce/`。
- 2026-10-08：重启 **仅 nce-2** 试点；脚本 `vocab_ocr/nce/pilot_nce2_from_excel.py`。
- **词性不进索引**：`pos` 只写 `_work` CSV；hit 为 `[book_id, lesson, zh]`。
- **人教 / NCE 同一格式、同一 `v:1`**（`vocab_ocr.shared.build_index.INDEX_VERSION`）；不搞多套版本号。

## Fog

- 三 / 四册是否沿用同一 Excel+课次表路径，待二册抽检满意后再定。
- 索引文件已落盘 EggplantDict `Resources/nce-vocab-index.min.json`；接入 `nce-*` 打标另票（EggplantDict）。

## Authority

| Doc | Role |
|-----|------|
| [`issues/01-nce-2-3-4-vocab-index.md`](./issues/01-nce-2-3-4-vocab-index.md) | 本票 |
| [`../english-vocab-ocr/`](../english-vocab-ocr/) | 项目票 #01（人教 PEP 格式先例） |
| [`../../data/vocab/nce-vocab-index.min.json`](../../data/vocab/nce-vocab-index.min.json) | nce-2 试点索引 |
| [`../../data/vocab/vocab-index.min.json`](../../data/vocab/vocab-index.min.json) | 现行 PEP 索引样例 |
