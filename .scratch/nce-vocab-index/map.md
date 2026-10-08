# nce-vocab-index（项目票 #02、#06、#07）— **resolved**（经典版 1–4 册）

四册 Excel 提供词头；第 1–4 册再用课文 PDF 核对 Lesson。与人教共用 `v:1` 三段 hit 形状；教材释义槽留空。

## Decisions so far

- 2026-10-08：曾整票取消并删除 `vocab_ocr/nce/`。
- 2026-10-08：重启 **仅 nce-2** 试点；脚本 `vocab_ocr/nce/pilot_nce2_from_excel.py`。
- **词性不进索引**：`pos` 只写 `_work` CSV；hit 为 `[book_id, lesson, zh]`。
- **人教 / NCE 同一格式、同一 `v:1`**（`vocab_ocr.shared.build_index.INDEX_VERSION`）；不搞多套版本号。
- 2026-10-08：用户要求先做经典版 1–4 册的册级索引。来源为 [lilinji/English](https://github.com/lilinji/English) 的四份新版 Excel；二册 Lesson 对齐留作历史试点。
- 2026-10-08：四册册级索引已生成并抽核，3357 个词头；每个 hit 保持 `[book_id, "", ""]`。见 [#02](./issues/01-nce-1-4-vocab-index.md)。
- 2026-10-08：[#06](./issues/02-lesson-index-from-pdfs.md) 定向读取课文 PDF 的词表页，核准第 2、3 册全部现有词头的课次；第 1 册 700/867 个词头获得课次，其余保留册级。
- 2026-10-08：[#07](./issues/03-nce4-lesson-index.md) 对照 314 页完整扫描版第四册的目录和词表，核准 784/784 个现有词头的课次；该册 9 个重复词保留两课 hit。

## Fog

- 第 1 册尚有 167 个词头未核准 Lesson，本机复核表见 `data/vocab/_work/nce-pdf-lessons/nce-1/review.csv`。
- 索引文件已落盘 EggplantDict `Resources/nce-vocab-index.min.json`；接入 `nce-*` 打标另票（EggplantDict）。

## Authority

| Doc | Role |
|-----|------|
| [`issues/01-nce-1-4-vocab-index.md`](./issues/01-nce-1-4-vocab-index.md) | #02 册级索引 |
| [`issues/02-lesson-index-from-pdfs.md`](./issues/02-lesson-index-from-pdfs.md) | #06 课次核对 |
| [`issues/03-nce4-lesson-index.md`](./issues/03-nce4-lesson-index.md) | #07 第四册完整扫描版课次核对 |
| [`../english-vocab-ocr/`](../english-vocab-ocr/) | 项目票 #01（人教 PEP 格式先例） |
| [`../../data/vocab/nce-vocab-index.min.json`](../../data/vocab/nce-vocab-index.min.json) | 正式新概念索引 |
| [`../../data/vocab/vocab-index.min.json`](../../data/vocab/vocab-index.min.json) | 现行 PEP 索引样例 |
