# 04: 人教英语索引释义与单元归属抽检

**项目票号（会话标题用）：** `#04`  
**Status:** resolved

## 目标

对已生成的 12 册人教英语索引做可复现的人工抽检，核对词头、中文释义和 Unit 归属，并找出 OCR 或页码映射造成的系统性错误。依据：[README 的索引说明](../../../README.md)、[原索引票 #01](01-english-vocab-ocr-index.md)、`vocab_ocr/pep/` 实现和 `data/vocab/vocab-index.min.json`。

## 范围与方法

- 从正式索引按固定随机种子在每册抽取普通词条，并额外抽取高风险条目：单元边界、疑似跨栏、已解析但未入索引的候选词。
- 逐条对照本机原始 PDF 的附录词表；初中再按词表所印页码核对教材目录/正文 Unit 边界。分别记录“词头/释义/单元/页码”是否正确，不以 OCR 文本作为唯一真值。
- 保存样本、来源定位、判定与错误示例；将系统性问题写成可复现的修复要求。若 12 册各一条对原页样本均暴露系统性错误，就停止本轮剩余样本的人工打分，待提取流程重建后复核。无法判定的条目单独标记，不算通过。
- 保持索引 schema `v:1`；不提交 PDF、图片、`_work/` 或分册 JSON。

## 验收

- [x] 12 册均有源 PDF 对照样本；随机样本和高风险样本可复现。
- [x] 已核的每个样本有四项判定及可定位的原书页；汇总错误数和主要错误类型。
- [x] README 说明复跑抽检的方法和索引当前的可靠性边界。

## 非目标

- 全量人工逐词校对。
- 新概念 2–4 册索引及 EggplantDict 接入。

## Comments

- 2026-10-08：用户要求新开 ticket，并在当前对话继续人教索引抽检。
- 2026-10-08：用户建议试用已在本机运行的 LM Studio Gemma 4 26B A4B 视觉模型。模型报告 `vision: true`。初中八上 PDF 126 页指定的 `disappointed`、`role`、`mushroom`、`ton` 四词与释义/印刷页码均正确分开。高中选必一 PDF 120 页整页指定词试验中，模型把页脚 112 错当词条页码、把 `barely` Unit 4 误作 Unit 5、漏掉 `assessment` 的一项释义；裁为右栏后，`barely` 正确，但单词 `assess` 的 Unit 4 在全栏转录中漏掉。视觉模型可作为重建方案，需要完整度与单元号复核。
- 2026-10-08：按用户建议在**完整原页**提示词中明确“右下角 112 是词表页码，词后括号数字才是 Unit”。复测不再误填 112，`barely` Unit 4 正确；但 `assessment` 被输出为 Unit 5（原页为 Unit 4），释义混入下一词 `assumption`。下一版优先整页视觉转录并在提示词中约束左右栏；仍须逐条复核，不能单凭提示词宣称正确。裁栏只用于诊断此类错误，不作为用户要求的默认方案。

## Answer

复跑命令：`python3 -m vocab_ocr.pep.audit`。固定种子 `20261008`，每册生成 2 条随机、1 条单元边界/引用、1 条疑似 OCR 串接、1 条已解析但未入索引候选，共 **60 条**，输出到忽略入库的 `data/vocab/_work/pep-audit-sample.csv`。表内的 `pdf` + `source_pdf_page` 定位原书；`candidate_*` 是当前索引/解析候选值。校对列 `word_ok`、`zh_ok`、`unit_ok`、`page_ok` 填 `yes/no/na/unclear`。命令默认拒绝覆盖已填表；确需重抽才用 `--force`。

本轮对照了 12 册各 1 条，共 **12 条**；均至少一项错误。这是随机与高风险混合样本，**不能据此估计全索引错误率**。由于双栏串接在每册均出现，按停止规则保留另 48 条未打分，等待重建后再抽检。具体原页与判定见上述 CSV，代表性例子：

| 册 | PDF 页 | 当前候选 | 原书核验 | 错误类型 |
| --- | ---: | --- | --- | --- |
| 七上 | 130 | `bicycle bike welcome` → Unit 4「受欢迎的」 | `bicycle` p.8、`welcome` p.11，均 Starter Unit 2 | 跨栏串词、释义/单元错 |
| 七下 | 109 | `perfect` p.22 | `perfect` p.19；同高度右栏 `sit-up` p.22 | 页码串栏 |
| 八上 | 126 | `disappointed role` →「作用；职能；角色」p.38 | `disappointed` p.36、`role` p.38 | 跨栏串词、释义错 |
| 八下 | 139 | `hide hid hidden interviewer` → Unit 6 | `hide` p.45 Unit 5；`interviewer` p.73 Unit 8 | 跨栏串词、单元错 |
| 九全 | 178 | `ring rang rung berlin` →「柏林」p.46 | `ring` p.44、`Berlin` p.46 | 跨栏串词、释义错 |
| 必修一 | 126 | `affair` → Unit w | `affair` Unit 5；右栏 `awkward` 是 w | 单元串栏 |
| 必修二 | 119 | `eighbourhood us eighborhood piano` →「钢琴」Unit 5 | `neighbourhood` Unit 2；`piano` Unit 5 | 跨栏串词 |
| 必修三 | 119 | `ba' ju'mn` →「白求恩」 | 原页无此词头；来自 `Henry Norman Bethune` 碎片 | 词头伪造 |
| 选必一 | 120 | `air conditioner assessment` →「评价；评定」Unit 4 | `air conditioner` Unit 2；`assessment` Unit 4 | 跨栏串词 |
| 选必二 | 124 | `bun` →「圆面包；小圆甜饼 GB) consume…」 | `bun` 的释义止于「小圆甜饼」 | 释义串栏 |
| 选必三 | 124 | `picasso rely i` →「依赖；依靠；信赖」Unit 2 | `Picasso` Unit 1；`rely` Unit 2 | 跨栏串词 |
| 选必四 | 119 | `barbecue abbr bbq chiang mai` →「清迈」 | `barbecue` 和 `Chiang Mai` 分在左右栏 | 跨栏串词 |

结论：当前 `vocab-index.min.json` 只证明 12 册已有机器生成的数据，**不具备直接打标所需的准确度**。下步优先使用整页视觉模型、明确左右栏读取顺序，逐条保留原始 PDF 页与印刷引用，并对词头、释义、单元号及覆盖率设校验门槛；完成后重建索引，再复核这 60 条及新的随机样本。
