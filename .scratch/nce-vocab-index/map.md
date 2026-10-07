# nce-vocab-index（项目票 #02）— **resolved**（经典版 1–4 册）

当前先用四册 Excel 直接生成册级索引；与人教共用 `v:1` 三段 hit 形状，课次与释义槽留空。

## Decisions so far

- 2026-10-08：曾整票取消并删除 `vocab_ocr/nce/`。
- 2026-10-08：重启 **仅 nce-2** 试点；脚本 `vocab_ocr/nce/pilot_nce2_from_excel.py`。
- **词性不进索引**：`pos` 只写 `_work` CSV；hit 为 `[book_id, lesson, zh]`。
- **人教 / NCE 同一格式、同一 `v:1`**（`vocab_ocr.shared.build_index.INDEX_VERSION`）；不搞多套版本号。
- 2026-10-08：用户要求先做经典版 1–4 册的册级索引。来源为 [lilinji/English](https://github.com/lilinji/English) 的四份新版 Excel；二册 Lesson 对齐留作历史试点。
- 2026-10-08：四册册级索引已生成并抽核，3357 个词头；每个 hit 保持 `[book_id, "", ""]`。见 [#02](./issues/01-nce-1-4-vocab-index.md)。

## Fog

- 如需恢复 Lesson 粒度，另行寻找可靠的课次来源并与四册 Excel 对齐。
- 索引文件已落盘 EggplantDict `Resources/nce-vocab-index.min.json`；接入 `nce-*` 打标另票（EggplantDict）。

## Authority

| Doc | Role |
|-----|------|
| [`issues/01-nce-1-4-vocab-index.md`](./issues/01-nce-1-4-vocab-index.md) | 本票 |
| [`../english-vocab-ocr/`](../english-vocab-ocr/) | 项目票 #01（人教 PEP 格式先例） |
| [`../../data/vocab/nce-vocab-index.min.json`](../../data/vocab/nce-vocab-index.min.json) | nce-2 试点索引 |
| [`../../data/vocab/vocab-index.min.json`](../../data/vocab/vocab-index.min.json) | 现行 PEP 索引样例 |
