# Agent notes — FreePEP fork

下载教材 / 整理 PDF / 改下载逻辑时：先读根目录 [`README.md`](./README.md)（本机用法与踩坑）。上游产品说明见 [`README.upstream.md`](./README.upstream.md)。

## 硬规则

1. **先打包直链，后 CLI**：`789txtlist.md` / `gztxtlist.md` / `txtlist.md`；缺书或 `p.20190723.xyz` 500 再用 `cli.py`。
2. **默认非高清**：不要加 `--hd`，除非用户明确要高清。
3. **代理分流**：`*.20190723.xyz` 可用 `127.0.0.1:7897`；`book.pep.com.cn` 逐页下载用直连。
4. **「文字版」≠ 无图纯文本**：是轻量整页 PDF；文字稿靠后续 OCR。
5. **落盘**：`downloads/789txt-main/`、`downloads/初中（六三学制）/<年级>/`、`downloads/高中/<学科>/`；勿把大体量 PDF 提交进 git。
6. **英语词源索引**：人教/新概念共用同一 schema（`v:1`，hit=`[book, unit|lesson, zh?page…]`，词性不进索引）。人教 `python3 -m vocab_ocr pep`；新概念试点 `python3 -m vocab_ocr.nce.pilot_nce2_from_excel`（仅 nce-2）。只提交 `data/vocab/vocab-index.min.json` / `nce-vocab-index.min.json`，勿提交 `_work/` / `books/` / PDF。消费方：EggplantDict `#21`。

## Agent skills

### Issue tracker

需求和 tickets 使用本地 Markdown，见 [`docs/agents/issue-tracker.md`](docs/agents/issue-tracker.md)。

### Triage labels

使用默认五种状态，见 [`docs/agents/triage-labels.md`](docs/agents/triage-labels.md)。

### Domain docs

单一上下文领域文档布局，见 [`docs/agents/domain.md`](docs/agents/domain.md)。
