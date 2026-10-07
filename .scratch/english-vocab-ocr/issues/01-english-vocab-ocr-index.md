# 01: 英语课本附录 OCR → 词源索引

**What to build:** 从已下载人教版初中/高中英语 PDF 书末单词附录 OCR，生成精简倒排索引（词 → 册 → 单元），供词典打标。

**Status:** resolved

## 范围

- 初中：七上/下、八上/下、九年级全一册
- 高中：必修 1–3、选择性必修 1–4
- 只 OCR 书末附录（初中约后 22%、高中约后 12%）
- 入库：`data/vocab/vocab-index.min.json`（与 NCE 共用 `v:1`）

## 验收

- [x] 12 册跑通并生成精简索引
- [x] `python3 -m vocab_ocr` / `--rebuild-index` 可复跑（README）
- [x] 索引已拷贝至 EggplantDict `Resources/pep-vocab-index.min.json`（`v:1`，2026-10-08 再覆盖）
- [x] 词典侧消费票：EggplantDict `#21`

## Answer

- 包：`vocab_ocr/`；产出约 3815 词键
- 例：`scenery` → 八上 Unit 1 + 选必二 Unit 4
- OCR 仍有脏字/单元偶发偏差，打标前宜抽样

## Comments

- 由临时 `.scratch/tickets/001-…` 迁入正式 local-markdown tracker。
- 2026-10-08：修复 A–Z 附录继承旧单元、单册预览覆盖全系列索引、空释义/明显 OCR 碎片入索引；从本地分册 JSON 重建正式索引。已核对初中五册目录页单元起始页，只有 PDF 页数匹配时才用作回退映射。
- 重建后仍覆盖 12 册：3124 个词键、3671 条 hit、0 条空释义。遗留 OCR 释义与单元仍需人工抽检。
