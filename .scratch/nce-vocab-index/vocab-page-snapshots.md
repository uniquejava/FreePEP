# 新概念英语词表页快照与重建笔记

关联 ticket：[#06](./issues/02-lesson-index-from-pdfs.md)、[#07](./issues/03-nce4-lesson-index.md)、[#08](./issues/04-preserve-vocab-pages.md)。

## 保存结果

原书目录：`/Users/cyper/Pdf/新概念课文1-4PDF/`。快照目录：原书旁的 `词表页快照/`。每册有一份 `nce-*-词表页.pdf` 和一份 `nce-*-页码清单.csv`，PDF 中每个收录课次都有书签。CSV 的 `snapshot_page`、`source_pdf_page` 是从 1 编起的页序，`lesson` 是课号，`printed_page` 是原书印刷页码；`role=continuation` 表示前一张词表的续页。

| 册 | 原 PDF | 词表页快照 | 词表课次 | 说明 |
| --- | --- | ---: | ---: | --- |
| 1 | `新概念1.pdf` | 115 页 | 115 课 | 29 个偶数课目标页是练习页，无独立词表。 |
| 2 | `新概念2.pdf` | 96 页 | 96 课 | 每课起始页有词表。 |
| 3 | `新概念3.pdf` | 67 页 | 60 课 | Lesson 34、38、39、43、45、51、58 各多一张续页。 |
| 4 | `新概念4-完整.pdf` | 52 页 | 48 课 | Lesson 27、32、33、37 各多一张续页。不要使用仅 49 页的 `新概念4.pdf`。 |

快照是用 `pypdf` 直接复制原 PDF 页面，没有重新截图、OCR 或降低分辨率。原 PDF 与导出 PDF 都不提交 Git；已核对的页码映射在仓库中的 [`vocab_ocr/nce/vocab_page_map.json`](../../vocab_ocr/nce/vocab_page_map.json)。导出不依赖本机忽略入库的 `_work/` OCR 缓存。

## 重建

在 FreePEP 根目录、装有 `requirements.txt` 中依赖的 Python 环境中运行：

```bash
.venv/bin/python -m vocab_ocr.nce.export_vocab_pages
# 只重建第四册：
.venv/bin/python -m vocab_ocr.nce.export_vocab_pages --book 4
```

若原书移到别处，使用 `--pdf-dir` 指定目录，必要时用 `--output-dir` 指定快照输出目录。脚本会先检查原 PDF 页数与页码表是否一致；不同版本应重新核对目录、页码和词表位置，不能套用旧映射。

## 下次提取词性时注意

1. 用 CSV 把快照页对应到 Lesson 与原书页；第 4 册完整扫描版目录在 PDF 第 28–29 页，印刷页码＋29 才是 PDF 页序。其余册的偏移和例外见 [README](../../README.md)。
2. 只识别页面上的 **New words and expressions** 词表（第四册个别页印成单数 **expression**）。第一册部分偶数课只有 **Written exercises**；练习或课文注释中也会出现单词和行号，不能据此认作新词。
3. 第 2–4 册词表常为双栏，传统 OCR 有时先读左栏、再读 **Notes on the text**、最后才读右栏。不要在 OCR 文本第一次遇到 **Notes** 时截断；需对照页面版面或分别读取两栏。
4. 原书词表含词性、音标和中文释义；现行 `v:1` 索引只保存词头、册/课来源与教材释义槽，**词性尚未入索引**。二次转录应另存候选与原页位置，再决定消费方的数据格式。

本次筛页不是从 OCR 命中数简单推断：曾目视检查无标题但有 OCR 匹配的页面，发现第一册练习页、第二册练习页，以及第三册只有注释和词汇练习的页面会产生假命中；只有确有印刷词表的续页被加入页码表。
