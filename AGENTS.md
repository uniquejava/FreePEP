# Agent notes — FreePEP fork

下载教材 / 整理 PDF / 改下载逻辑时：先读根目录 [`README.md`](./README.md)（本机用法与踩坑）。上游产品说明见 [`README.upstream.md`](./README.upstream.md)。

## 硬规则

1. **先打包直链，后 CLI**：`789txtlist.md` / `gztxtlist.md` / `txtlist.md`；缺书或 `p.20190723.xyz` 500 再用 `cli.py`。
2. **默认非高清**：不要加 `--hd`，除非用户明确要高清。
3. **代理分流**：`*.20190723.xyz` 可用 `127.0.0.1:7897`；`book.pep.com.cn` 逐页下载用直连。
4. **「文字版」≠ 无图纯文本**：是轻量整页 PDF；文字稿靠后续 OCR。
5. **落盘**：`downloads/789txt-main/`、`downloads/初中（六三学制）/<年级>/`、`downloads/高中/<学科>/`；勿把大体量 PDF 提交进 git。
