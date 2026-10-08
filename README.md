# FreePEP（本机用法）

本仓库 fork 自 [siknet/FreePEP](https://github.com/siknet/FreePEP)。  
上游说明见同目录 **[README.upstream.md](./README.upstream.md)**（原版 README 备份）。

这里的 README 只记**我们实际踩过的坑和下法**，按它做能少绕路。目标：先拿到可用 PDF，再另用 OCR 做成文字稿。

---

## 先分清三个概念

| 说法 | 实际含义 |
|------|----------|
| 打包「纯文字版」(`*txtlist.md`) | 预合成 PDF 直链，体积较小；**不是**无图纯文本 |
| 打包「图文版」(`*piclist.md`) | 另一档预合成 PDF，通常更重 |
| CLI「普通 / 高清」 | `mobile`（默认）vs `--hd`→`large`；都是整页 JPG 拼 PDF |

人教社电子课本本质是**整页图片**。要可检索文字稿，需另做 OCR，本工具只负责 PDF。

---

## 推荐下载顺序（少走弯路）

1. **优先**用仓库根目录打包列表的直链（文字版）：
   - 初中：[`789txtlist.md`](./789txtlist.md)
   - 高中：[`gztxtlist.md`](./gztxtlist.md)
   - 小学：[`txtlist.md`](./txtlist.md)
2. 直链失败或缺书时，再用 CLI 逐页合成（`python cli.py ...`，**不要**加 `--hd`，除非明确要高清）。
3. 需要整学段归档时，可参考上游 `download_all.py`；我们当前手工按学科/年级放进 `downloads/`。

### 代理怎么用

| 目标 | 建议 |
|------|------|
| `*.20190723.xyz` 打包直链 | 用本机代理（例：`http://127.0.0.1:7897`） |
| `book.pep.com.cn` CLI 逐页 | **直连更快**；过 WAF 后单页约 80–110ms，代理略慢 |

### 直链域名经验

- `n.20190723.xyz`：可用，速度快（约 1–2s/本）。
- `p.20190723.xyz`：曾大面积 **HTTP 500**，重试无用 → 改走 CLI。
- 其它镜像偶尔出现，失败同样回退 CLI。

### CLI 注意

- 学段参数用完整名：`--xd "初中（六三学制）"` / `"高中"` 等。
- `pep_core.map_book_xd` 曾有 bug：缓存里已是「初中（六三学制）」时会被误标成小学，导致筛选为空。本 fork 已修（匹配含「初中」即可）。若上游未合入，拉新代码后确认该修复还在。
- 依赖：`pip install -r requirements.txt` 且 `playwright install chromium`（macOS 缺 Chromium 会「任务完成但无 PDF」）。
- CLI 和 `download_all.py` 现在只在页数齐全、PDF 可读取后发布文件；失败页保留在 `temp_pages/` 供续传。成功下载会生成同名 `.pdf.freepep.json` 完成清单，供下次快速跳过。旧 PDF 无清单时先读取教材总页数再校验；校验不通过会重新下载。

---

## 本机目录约定

```text
downloads/
├── 789txt-main/              # 初中主课文字版（扁平，便于批量 OCR）
├── 初中（六三学制）/
│   ├── 七年级/ …             # 按年级归档（与 FreePEP 树一致）
│   ├── 八年级/ …
│   └── 九年级/ …
└── 高中/
    ├── 英语/
    ├── 语文/
    └── 数学/
```

- `downloads/`、`temp_pages/` 不入库（体积大）。
- 初中主课范围（我们用过的）：语数英 + 物化政（道德与法治）史地生；不含音体美等。

---

## 已验证过的命令骨架

```bash
# 仓库位置
cd ~/code/FreePEP

# 打包直链（示例：用代理；按 *txtlist.md 解析后 curl/脚本下载）
export https_proxy=http://127.0.0.1:7897 http_proxy=http://127.0.0.1:7897

# CLI 补缺：普通版、免确认（人教社请直连，可先 unset 代理）
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY
python cli.py --xd "初中（六三学制）" --xk "语文" --nj "七年级" -o ./downloads/789txt-main --flat -y
python cli.py --xd "高中" --xk "英语" -o ./downloads/高中/英语 --flat -y
```

高清仅在明确需要时：`python cli.py ... --hd`。

---

## 英语单词来源索引（OCR）

人教 PEP：先读目录页定位附录词表，再 OCR。代码在 `vocab_ocr/pep/`（共享工具 `vocab_ocr/shared/`）。产出：[`data/vocab/vocab-index.min.json`](./data/vocab/vocab-index.min.json)。

```bash
brew install poppler tesseract tesseract-lang   # pdftoppm + eng/chi_sim
python3 -m vocab_ocr pep --all                 # 缺册才 OCR；旧 OCR 结果只生成预览
python3 -m vocab_ocr pep --book junior-8a --force  # 单册预览写入 data/vocab/_work/preview/
python3 -m vocab_ocr pep --rebuild-index       # 仅从 books/*.json 重打包旧 OCR 预览
```

人教与新概念共用索引 schema `v: 1`：每条 hit 末尾是中文释义字符串；没有可靠教材释义时为空字符串。同一词在多单元或多课出现时保留多条 hit。词性不进索引。

```json
{
  "v": 1,
  "books": { "junior-8a": "英语八年级上册" },
  "w": {
    "landscape": [["junior-8a", "1", "风景；景色"], ["junior-8a", "8", "风景；景色"]]
  }
}
```

`w[word]` → `[book_id, unit|lesson, zh]`，有页码时为 `[book_id, unit|lesson, page, zh]`。旧 OCR 的 `--book`、`--all` 和 `--rebuild-index` 只在忽略入库的 `_work/` 生成预览，不覆盖正式索引。`_work/`、分册 `books/*.json` 不入库。空释义与明显 OCR 碎片会被排除；初中目录识别失败时，对已核对页数的本机版本使用目录页单元起始页。

**质量状态（2026-10-08）**：正式索引虽覆盖 12 册，但尚不能直接作为可靠的词源标签。按固定种子和高风险规则抽取的 60 条候选中，先对照 12 册 PDF 各核 1 条，12 条均发现至少一项错误；这是混合抽样，不能当作总体错误率。主要是双栏词表被传统 OCR 串成一行，造成词头、释义、页码和单元号串栏。详见 [抽检 ticket #04](./.scratch/english-vocab-ocr/issues/04-pep-index-spot-check.md)。重建前不要将它视为已校准索引。

复跑抽检表（不覆盖已有人工判定）：

```bash
python3 -m vocab_ocr.pep.audit
# 输出 data/vocab/_work/pep-audit-sample.csv；要重新抽空白表才加 --force
```

逐行打开 CSV 的 `pdf` 与 `source_pdf_page`，以原书图片为准核词头和中文释义。初中 A–Z 的 `p.` 页码再对目录 Unit 起始页；高中直接核词后的括号单元号。`word_ok`、`zh_ok`、`unit_ok`、`page_ok` 分别填 `yes/no/na/unclear`，疑点写 `notes`。本机 LM Studio 的 Gemma 4 26B 视觉模型在小样本里能分开双栏词，但仍漏释义或误读单元号；可用作下一版提取候选，必须再做 PDF 对照和覆盖率检查。

整页视觉转录是尚未完成的实验流程。复制 `.env.sample` 为本机 `.env`，设置 `LM_STUDIO_BASE_URL`，并先在 LM Studio 中启动对应视觉模型。`python3 -m vocab_ocr pep --vision --book junior-8a --vision-page 126` 只生成 `_work/vision/` 候选；`--check-vision` 报告质量阻碍。`--publish-vision` 仅在 12 册及原页人工复核全部过关时发布，目前不能据此更新正式索引。

新概念经典新版 1–4 册的词头来自 [lilinji/English](https://github.com/lilinji/English) 的四份 Excel，再对照本机课文 PDF 的目录页和每课词表页填入已核对的 Lesson。第 4 册必须使用保留封面和前言的 `新概念4-完整.pdf`；同目录的 49 页 `新概念4.pdf` 不是这本完整扫描版。源仓库 README 标注 [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)；本索引是来源词表的派生数据，按来源许可使用，与仓库代码的 MIT 许可分开。不提交原 Excel、PDF 或 OCR 缓存。每条 hit 保持 `v:1` 的三段结构 `[book_id, lesson, ""]`；未确认课次时第二段为空。Excel 的通用词典释义不等于教材释义，所以第三段仍为空。

```bash
python3 -m vocab_ocr.nce.align_pdf_lessons 2 --pdf-dir '/Users/cyper/Pdf/新概念课文1-4PDF'
python3 -m vocab_ocr.nce.align_pdf_lessons 3 --pdf-dir '/Users/cyper/Pdf/新概念课文1-4PDF'
python3 -m vocab_ocr.nce.align_pdf_lessons 1 --pdf-dir '/Users/cyper/Pdf/新概念课文1-4PDF'
python3 -m vocab_ocr.nce.align_pdf_lessons 4 --pdf-dir '/Users/cyper/Pdf/新概念课文1-4PDF'
python3 -m vocab_ocr.nce.build_book_index --source-dir '/path/to/8.新概念英语' --pdf-lessons-work data/vocab/_work/nce-pdf-lessons
```

默认 Excel 目录是 `~/code/English/8.新概念英语/`，输出为 [`data/vocab/nce-vocab-index.min.json`](./data/vocab/nce-vocab-index.min.json)。缺任一册 Excel 时生成器会失败，保留现有索引。`align_pdf_lessons` 只读目录指定的课次页：第 2 册 PDF 页序＝印刷页码＋3；第 3 册＝＋2；第 1 册 Lesson 1–72＝＋4、73–144＝＋8，词表在课文起页的下一页。第 4 册目录在 PDF 第 28–29 页，Lesson 1–48 的起始印刷页码间距不固定，PDF 页序＝印刷页码＋29；词表可能从课文起页或下一页开始，还可能跨栏或续页。第 2、3、4 册偶数课也有词表；第 1 册部分偶数课没有。OCR 候选和复核表写在忽略入库的 `data/vocab/_work/nce-pdf-lessons/nce-*/`。不加 `--pdf-lessons-work` 时，生成器会重建纯册级索引。

**核对进度（2026-10-08）**：第 2、3、4 册现有 Excel 词头分别 840/840、1050/1050、784/784 已有课次，少量 OCR 漏读词已对照 PDF 目视补录；同一词在多课词表出现时保留多条 hit。第 1 册 867 个词头中有 700 个直接匹配或目视核对词表，余下 167 个保留空课次，见本机 `nce-1/review.csv`。第 2 册 Excel `content` 对应课文词表 `contents`、`the press` 对应 `Press`，两项已目视核到课次，词头仍保持 Excel 原样。原二册 `python3 -m vocab_ocr.nce.pilot_nce2_from_excel` 只写入 `_work/nce-2/` 历史预览，不覆盖正式索引。票在 [`.scratch/english-vocab-ocr/`](./.scratch/english-vocab-ocr/)（`#01`）、[`.scratch/nce-vocab-index/`](./.scratch/nce-vocab-index/)（`#02`、`#06`、`#07`）。

供后续词性等二次处理的**词表页 PDF 快照**保存在原书目录旁的 `词表页快照/`：四册分别 115、96、67、52 页，附快照页序到 Lesson／原书页码的 CSV。可用 `python3 -m vocab_ocr.nce.export_vocab_pages` 从原书无损重建；页码映射与筛页注意事项见 [快照笔记](./.scratch/nce-vocab-index/vocab-page-snapshots.md)（#08）。快照和原书均不入 Git。

**后续需求（#09，尚未实施）**：[教材词表页 PDF 与词源索引一键跳转](./.scratch/vocab-page-links/issues/01-vocab-page-pdf-links.md)覆盖人教 12 册与新概念 4 册，每册一份完整词表页快照，共 16 份。EggplantDict 点击教材出处时打开实际印有该词的完整原页，保留教材版面与上下文。二次识别另用词表区域裁图；计划将已核对的页码关系、区域坐标与阅读顺序保存在 `data/vocab/vocab-page-map.json`，派生裁图与识别候选保存在 `data/vocab/_work/vocab-page-regions/<book_id>/`。本票准备素材和映射，新增音标、词性、释义转录由后续任务处理。

---

## 远程

- `origin` → 本 fork（`uniquejava/FreePEP`）
- `upstream` → `siknet/FreePEP`

上游功能、WebUI、参数全集仍以 [README.upstream.md](./README.upstream.md) 为准。
