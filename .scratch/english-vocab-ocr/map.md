# english-vocab-ocr

人教版初中/高中英语课本附录 OCR → 词源倒排索引（含中文释义）。

## Decisions so far

- 流水线在 `vocab_ocr/pep/`；共享工具 `vocab_ocr/shared/`。
- **先读目录页**定位附录词表印刷页，再 OCR；TOC 失败才回退书末密度扫描。
- 入库 `data/vocab/vocab-index.min.json`（与 NCE 共用 `v:1`，hit 末尾带中文释义；一词多单元多条）；`_work/`、`books/` 不提交。
- 消费方：EggplantDict `#21`（查词自动打标）。
- 新概念二册试点见项目票 **#02**（[`../nce-vocab-index/`](../nce-vocab-index/)）；三、四册未做。

## Fog

- OCR 双栏/脏字仍有误差；打标前宜抽样校对。
- 单元映射（尤其初中）偶发偏差。
- 部分初中目录 OCR 弱，可能仍走 densify_fallback。

## Authority

| Doc | Role |
|-----|------|
| [`README.md`](../../README.md) §英语单词来源索引 | 复跑命令 |
| [`issues/`](./issues/) | Tickets |
