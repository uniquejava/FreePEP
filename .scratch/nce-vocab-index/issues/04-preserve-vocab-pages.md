# 04: 保存四册新概念英语词表页快照与重建方法

**项目票号（会话标题用）：** `#08`
**Type:** task
**Status:** resolved

## 目标

从本机原始 PDF 重新导出第 1–4 册确有词表内容的页，保留为可用于后续词性等二次处理的 PDF 快照。保存页码映射和复跑方法，避免临时截图或 OCR 缓存丢失后重新摸索。

## 范围与约束

- 来源为 `/Users/cyper/Pdf/新概念课文1-4PDF/` 的前三册 PDF 和 `新概念4-完整.pdf`。
- 每册保存独立的词表页 PDF 与清单，清单指出原书 PDF 页序、印刷页码、关联 Lesson、快照页序以及选择依据。双栏词表跨页时保留续页。
- 快照放在原始 PDF 目录下，不纳入 Git；仓库只保存可复跑脚本和简明方法笔记。
- 验证快照可读取、页数与清单一致，抽查首尾课和续页。

## 依赖

- 第 1–3 册定位依据：[#06](./02-lesson-index-from-pdfs.md)。
- 第 4 册目录与页码依据：[#07](./03-nce4-lesson-index.md)。

## Comments

- 2026-10-08：用户希望保留确实有用的词表页 PDF 快照，供后续词性等处理；若临时快照已丢失，就记录方法。原书和 OCR 记录仍在，可重新导出。

## Answer

- 原书仍在；从原 PDF 无损复制词表页到 `/Users/cyper/Pdf/新概念课文1-4PDF/词表页快照/`。四册分别 115、96、67、52 页，共 330 页；各册附 CSV 页码清单和 Lesson 书签。
- 第一册 29 个没有独立词表的练习页已剔除；第三册 7 张、第四册 4 张确有词表的续页已保留。对易误判的无标题页作了目视检查，避免把练习里的行号当作词表。
- 已核对页码映射提交为 [`vocab_page_map.json`](../../../vocab_ocr/nce/vocab_page_map.json)，可用 [`export_vocab_pages.py`](../../../vocab_ocr/nce/export_vocab_pages.py) 从原书重建；做法见 [快照笔记](../vocab-page-snapshots.md)。
- 导出 PDF 均可读取，页数、Lesson 书签与 CSV 行数一致；抽看首尾课和跨页词表无误。全套测试 `.venv/bin/python -m pytest -q`：65 passed，1 条上游弃用警告。
