# 01: 避免提交关联外部票据

**项目票号（会话标题用）：** `#11`
**Type:** task
**Status:** resolved

## 目标与范围

FreePEP 是用户独立开发的 fork。查明最近提交在 GitHub 显示 `siknet#10` 等链接的原因，并固定提交消息的本地票号格式，避免与上游或任何外部 issue/PR 产生关联。

## 依据与依赖

- 用户 2026-10-09 提供的 GitHub 提交列表截图。
- [项目规则](../../../AGENTS.md)、[本地 tracker](../../../docs/agents/issue-tracker.md)。
- 本地原始提交消息与 GitHub 页面中的实际链接目标。
- 无实现依赖；用户已于 2026-10-09 明确授权重写有问题的提交消息并 force push。

## 验收

- [x] 核对原始提交消息及链接目标，说明前缀的产生原因。
- [x] 提交消息使用 `FP-010` 等本地票号；多票使用 `FP-005、FP-009`，不使用 GitHub issue/PR 引用语法。
- [x] 规则明确 ticket 只指 `.scratch/` 的本地 Markdown；聊天标题继续遵守项目票号规则。
- [x] 保留既有无关 `AGENTS.md` 改动；最近 8 个提交只调整消息，本票规则单独提交，经远端 SHA 核对后用 `force-with-lease` 推送。

Git 授权范围：重写最近 8 个本地票号提交的消息、单独提交本票规则，使用带明确旧远端 SHA 的 `force-with-lease` 推送 `origin/main`。保留既有无关 `AGENTS.md` 改动，不修改上游提交。

## Comments

- 2026-10-09：用户明确本仓库由本人独立开发，不希望与任何外部 ticket 关联。
- 2026-10-09：用户明确要求修改后重新提交有问题的 commit message，并 force push。

## Answer

原始消息只有本地票号 `#NN`。GitHub 的 fork 提交页面将它们自动解析为上游引用，已实际核对 `siknet/FreePEP/issues/10` 等链接及 `siknet/FreePEP/pull/6`。

最近 8 个提交全部改用 `FP-NNN`，多票分别加前缀；各提交的 tree、作者与时间保持原样。项目规则与 tracker 说明单独提交，既有无关 `AGENTS.md` 改动仍在工作区。用户授权的 `force-with-lease` 推送已成功，远端 SHA 已核对；GitHub 页面显示 9 条 `FP-` 消息，上游 issue/PR 关联链接为 0。旧 HEAD 保留于本地恢复引用 `refs/backup/fp-ticket-messages-20261009`。
