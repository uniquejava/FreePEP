# FreePEP 项目规则

本文件补充全局 `~/.agents/AGENTS.md`，只记录 FreePEP 的差异和资料入口。全局规则未加载时先读取该文件；冲突时按用户当前指令、项目规则、全局规则的顺序执行。

## Git 授权

- 默认在 `main` 工作；分支选择不授予 commit 或 push 权限。
- 开票、实现、修复、整理文档等任务完成后，将结果保留在工作区。只有用户明确要求 commit 时才提交；只有用户明确要求 push 时才推送。commit 授权不包含 push 授权。
- 按用户授权的具体范围操作，保留其他未提交改动。用户要求撤销提交或推送时，先核对相关提交和远端状态，再执行对应撤销。

## 教材下载与 PDF

下载教材、整理 PDF 或修改下载逻辑前，先读 [README.md](./README.md) 的本机用法与踩坑；上游产品说明见 [README.upstream.md](./README.upstream.md)。

- 先用打包直链列表：初中 [789txtlist.md](./789txtlist.md)、高中 [gztxtlist.md](./gztxtlist.md)、小学 [txtlist.md](./txtlist.md)。缺书或直链失败再用 `cli.py`。
- 默认使用普通版；仅在用户明确要求高清时加 `--hd`。
- `*.20190723.xyz` 可用本机 `7897` 代理；`book.pep.com.cn` 逐页下载走直连。其余代理范围、重试和下载速度要求继承全局规则。
- “文字版”是轻量整页 PDF；需要文字稿时另做 OCR。
- 教材放在 `downloads/789txt-main/`、`downloads/初中（六三学制）/<年级>/` 或 `downloads/高中/<学科>/`；已保存的词表页快照按相关票据约定存放。

## 英语词源索引与生成数据

生成、更新或消费索引前，先读 [README「英语单词来源索引」](./README.md#英语单词来源索引ocr)，确认来源、当前质量、schema 和完整复跑命令。

- 人教与新概念共用 schema。v2 的 `pos_version: 1` 扩展按教材出处保存印刷词性、分义及区域证据，契约见 README；同词在多册、多 Unit/Lesson 的命中应保留。新增字段时，明确版本及消费端兼容方案。
- 人教和新概念的现行正式生成器是 [reference.py](./vocab_ocr/reference.py)，按 README 从完整的直接视觉复核记录生成 v2 索引、映射及完整页 PDF 资料包。旧 OCR、[build_book_index.py](./vocab_ocr/nce/build_book_index.py) 和二册 Excel 试点仅作历史预览，不能降级覆盖正式结果。
- 人教旧 OCR 及视觉候选的质量状态见 README；单册预览、未复核候选和不完整语料不能覆盖正式全册索引。
- 允许纳入版本控制的正式词表数据为 `data/vocab/vocab-index.min.json` 与 `data/vocab/nce-vocab-index.min.json`。代码、测试、文档及可复跑的页码映射也可纳入；commit/push 仍须遵守上面的授权规则。
- 原始 Excel、PDF、裁页 PDF、渲染图片、OCR 缓存，以及 `data/vocab/_work/`、`data/vocab/books/` 保留在本机，不纳入 Git。来源许可和本机输出位置见 README 与相关票据。
- 消费方是 EggplantDict。跨仓库接入前读取其项目规则和相关词源票据，并同步明确的数据契约。

## Tickets 与领域文档

- 创建或更新需求票据时，读 [issue-tracker.md](./docs/agents/issue-tracker.md) 和 [triage-labels.md](./docs/agents/triage-labels.md)；本项目使用 `.scratch/` 中的本地 Markdown tracker。
- 现有票据有特性目录内的文件序号和全仓库项目票号。新票先检查 `.scratch/` 中已用的项目票号；两者不同时，写明“项目票号（会话标题用）”，标题使用该票号。票据内容、链接和标题其余要求继承全局规则。
- 探索领域术语或设计边界时，读 [domain.md](./docs/agents/domain.md)，按其中规则查阅已有 glossary 和 ADR。

## 本地票号与提交消息

- 本仓库是用户独立开发的 fork，Ticket 仅指 `.scratch/` 中的本地 Markdown 票据；票据关联使用本地文件路径。
- commit message 使用 `FP-010 简短中文主题`，多票使用 `FP-005、FP-009 简短中文主题`。`FP-010` 对应本地项目票号 `#10`；会话标题仍按全局规则使用 `#10`。
- commit message 不使用裸 `#NN`、`owner/repo#NN`、外部 issue/PR URL 或关闭外部票据的关键字，避免 GitHub 将本地票号解析为上游或其他仓库的关联。
