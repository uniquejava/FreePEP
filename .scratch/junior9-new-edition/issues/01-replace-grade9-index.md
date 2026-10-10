# 01: 新版九年级上下册替换全一册索引

**项目票号（会话标题用）：** `#12`
**Type:** task
**Status:** resolved

## 目标与范围

APP只展示新版英语九年级上／下册，不保留旧全一册或版本选择。仅重新识读九年级，其余15册的命中、映射、PDF和新概念索引复用。新版ID为`junior-9a`／`junior-9b`，共用「九年级」标签；不拆分旧14 Unit数据，不沿用旧证据。

## 依据与依赖

- [现行生成、数据契约与复跑命令](../../../README.md#英语单词来源索引ocr)
- [#13 九下来源核验与中文阅读修复](02-verify-and-clarify-lower-vocab.md)
- [#09 原页资料包](../../vocab-page-links/issues/01-vocab-page-pdf-links.md)、[#10 印刷词性](../../vocab-pos/issues/01-printed-pos-from-regions.md)
- [人教社新版结构介绍](https://www.pep.com.cn/xw/zt/hd/12/xjcjs/cz/202510/t20251024_2004130.html)：九上8 Unit、九下5 Unit及2个戏剧。
- [EggplantDict #56 接入与验收](../../../../eggplant-projects/EggplantDict/.scratch/mvp/issues/56-grade9-new-edition-resources.md)

## 实现与契约

1. 直接查看原书图片转录；脚本只渲染、存储、校验和打包，不调用OCR或识别模型。
2. 新册记录在`data/vocab/_work/junior9-index/`；其他15册记录仍在`reference-rebuild/`。冻结基准为`downloads/vocab-reference-before-grade9/`，现行完整包唯一位置为`downloads/vocab-reference/`。
3. 保持`v:2`／`pos_version:1`。人教新增`gloss_version:1`：有辅助中文的命中携带`gloss_source`，分义沿用来源，合并身份包含来源。实现与校验见[gloss.py](../../../vocab_ocr/gloss.py)。
4. 九下疑点词性标`unresolved`并保留原字及说明；正文引用页照录。跨表确认Unit时用`unit_source_pdf_page`／`reference_note`绑定同书同词的清楚对照，不能静默改页码。
5. 九下阅读快照使用清晰阅读版，原书身份和词性证据仍绑定108页原文件。`reading_derivative`、`pdf_note`保留来源元数据；APP不常驻显示技术说明，逐释义辅助来源仍显示。
6. 草稿不能发布／安装，含退役`junior-9`的计划／资料包不能重新正式build／publish／install；旧基准仅用于校验与增量复用。

## 验收

- [x] 两册目录、词表范围、所有候选尾页均核实；九下来源性质与限制见#13。
- [x] 词头、释义、Unit／正文页、词性及65个区域证据完成直接视觉复核，未核不冒充已确认。
- [x] 正式索引／映射／PDF仅含新版上下册，旧全一册退出现行资源。
- [x] 其他15册命中／映射完全一致，PDF和NCE索引字节不变。
- [x] 生成端完整校验、96项测试及9个子测试通过。
- [x] 词典整套资源、7,057个联想键、52项Release测试、核心界面验收和唯一Release实例恢复完成。
- [x] 续修移除两张词表首页的重影注释与APP常驻技术说明；新包已同步并重启。
- [x] 文档统一现行路径；重复包、草稿和预览PDF清理完成。未commit／push。

## Answer

现行包为17册／545词表页，人教13册5,325查询词头，新概念4册3,359词头。九上源117–136页共20页／922条逐页记录（750印刷、172未标）；九下源94–104页共11页／456条（353印刷、91未标、12待核）。9a／9b的目录分别为8／5 Unit。

九下26个不同出处带中文来源说明，6条异常原印引用保留对照依据。12条待核为reunite、recreate、ban、diligence、cherish、两表inform、graduate、row、pound、trap首义、whatever；原印`regair`与`Hong Kong SAN, China`保留，疑点写入证据说明，不从另一位置或通用语法推断改字。

词典#56已完成整包安装与顶层索引同步。上下册书名／Unit、共用标签、来源分组、待核词性、异常页码和完整阅读页通过隔离桌面验收；临时词库已清理，正常词库恢复到固定build路径的唯一Release实例。本次续修仅更改九下两条顶部注释，词义／词性／位置和其他16册不变。

联想键与候选由测试确认；微信拼音输入法下自动输入未确认浮层，实际交互留待用户体验，不据此判定产品故障。
