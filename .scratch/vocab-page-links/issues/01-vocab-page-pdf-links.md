# 01: 全册视觉重建与教材原页资料包

**项目票号（会话标题用）：** `#09`
**Type:** task
**Status:** claimed

## 目标

用户在 EggplantDict 查词时，从教材出处打开实际印有该词的完整原页，保留书页版面、注释与页码。16 册词表的词头、课次、教材中文释义与逐词原页关系全部重新识读；索引需要的 PDF 随应用一起打包，正常使用无需另找原书。

## 已确认范围

- 人教版 12 册（初中 5 册、高中必修 3 册、选必 4 册），新概念经典版 1–4 册，共 16 册。
- 用户指定由当前 Codex 自己看图识别；已授权子代理并行。脚本仅渲染、保存、校验与打包，不调用本地模型或 OCR 服务，不用旧索引/Excel 当新转录来源。
- 每册一份 PDF，按原书顺序汇集该册全部完整词表页及必要续页，共 16 份。单元词表、A–Z 表、小学补充词表和参考词表均检查；不含词表的练习、语法、后记等逐页分类排除。
- 从源 PDF 无损抽页，保留完整原页、尺寸、旋转和清晰度；二次处理另外导出词表区域裁图。PDF 不提交 Git，本票不发布教材公共下载。
- 承接 [人教 #05](../../english-vocab-ocr/issues/05-pep-visual-index-rebuild.md)。消费端实施见 [EggplantDict #25](../../../../eggplant-projects/EggplantDict/.scratch/mvp/issues/25-textbook-reference-bundle.md)。保留消费端 [#24 的 Tooltip 决策](../../../../eggplant-projects/EggplantDict/.scratch/mvp/issues/24-textbook-tag-popover.md)，标签右键选择完整原页。

## 来源与数据契约

源书由 [`pep/catalog.py`](../../../vocab_ocr/pep/catalog.py) 和 [`nce/vocab_page_map.json`](../../../vocab_ocr/nce/vocab_page_map.json) 定位。新概念四册必须使用完整扫描版，第四册为 `新概念4-完整.pdf`。生成器见 [`vocab_ocr/reference.py`](../../../vocab_ocr/reference.py)。

1. 先冻结源书 SHA-256、页数和候选页范围；每页直接复核后记录为词表或非词表。发布前必须全部检查完，源文件变化或任何缺页时停止，保留现有正式产物。
2. `v:2` 命中为对象：`book`、`unit`、`zh`、`headword`、可选正文 `page`、`pdf_pages` 与 `references`（`pdf_page`、`region_id`）。词性、音标不进入正式索引。同词多册、多课、异义和跨页保留；印刷拼法/缩写可作为同一出处的查询别名。没有课次的参考词表用 `reference`，不猜 Unit。
3. `pdf_pages` 是抽页后 PDF 的 1 起始页序；统一映射分别记录快照页序、源 PDF 页序和印刷页码，不能用初中的正文 `p.` 当词表 PDF 页。单个词释义跨页时关联两页。
4. 区域采用**可见页方向、左上角原点的归一化坐标**。记录稳定区域 ID、框、数组阅读顺序、原页尺寸与旋转。区域覆盖完整词头、音标、词性和多行释义；双栏按实际版面划分，跨栏词表可用整体区域。
5. 同目录的 `manifest.json` 校验两份索引、页码映射与全部 PDF；两份索引各有 `pdfs` 元数据，文件名为相对路径。严格核对版本、文件集合、校验值、PDF 页数、映射顺序、所有词条目标/区域与课次。旧 `v:1` 不能被当作带原页的索引。

## 保存位置与命令

- 逐页源证据：`data/vocab/_work/reference-rebuild/sources.json` 与 `books/<book_id>/pages/<源页>.json`。保留词头、教材释义、课次、区域、源书校验值和 `reviewed_by: codex-direct-vision`；不入 Git。
- 可移动运行资料包：`downloads/vocab-reference/`，包含 `pep-vocab-index.min.json`、`nce-vocab-index.min.json`、`vocab-page-map.json`、`manifest.json` 和 `pdf/<book_id>-vocab.pdf`。不依赖源书路径或 `_work/`。
- 小文件正式产物：`data/vocab/vocab-index.min.json`、`nce-vocab-index.min.json`、`vocab-page-map.json`，可提交 Git。
- 二次处理区域图及来源 JSON：`data/vocab/_work/vocab-page-regions/<book_id>/`。JSON 记录区域 ID/框、源书与快照校验值、三种页码、映射校验值和渲染 DPI。以后识别结果应引用这些证据，不代替用户阅读的完整原页。
- 消费端构建目录：`EggplantDict/Resources/TextbookReferences/`；Xcode 按完整目录打包到 `.app/Contents/Resources/TextbookReferences/`，PDF 不入 Git。

```bash
.venv/bin/python -m vocab_ocr.reference status
.venv/bin/python -m vocab_ocr.reference build
.venv/bin/python -m vocab_ocr.reference validate
.venv/bin/python -m vocab_ocr.reference publish
.venv/bin/python -m vocab_ocr.reference regions --dpi 200
.venv/bin/python -m vocab_ocr.reference install \
  --destination ../eggplant-projects/EggplantDict/EggplantDict/Resources/TextbookReferences
```

`build` 只组合已复核记录，不运行识别；`regions` 可从完整资料包重新导出裁图。`install` 校验后整体替换应用资源目录，失败时保留旧目录。消费端 PDFKit 直接定位精确完整页，应用移到其他位置后仍可离线使用。

## 验收

- [x] 16 册所有候选页直接查看、转录或分类，正式索引全部有逐页源证据；核对人教 #04 风险样本，说明原书自身的印刷冲突。
- [x] 16 份无损词表页 PDF，清单页数/顺序/续页/源书校验一致；同词多册、多课和跨页目标均有效。
- [x] 区域映射与二次处理来源信息已生成，双栏、多行释义和跨页案例裁图不截断；可从移动后的资料包重建。
- [x] v2 生成/消费端拒绝错版本、缺文件、坏校验值、越界页和无效区域，测试覆盖安装与搬动目录。
- [ ] 当前 EggplantDict 构建包含全部 16 份 PDF，不依赖原书或 OCR 缓存；实际查词的原页入口和优化构建验收通过。
- [x] README 与双方票据一致；原书、快照、图片与 `_work/` 不进入 Git。用户已于 2026-10-08 授权整理文档并提交，未授权推送。

## 当前结果

728 张候选页全部逐页识读或分类：542 张词表页、186 张非词表页，保存 14,438 条原页行及续页关系。已生成 16 份完整页 PDF、917 个二次处理区域及来源 JSON，运行资料包约 67.1 MiB。正式查询词头为人教 5,143、新概念 3,359；出处命中为人教 5,986、新概念 3,629。542 张抽页的内容流、页面边界和旋转信息与源页一致。

生成端 77 项测试和消费端 190 项测试通过，当前 Release 应用资源目录校验通过，确认包含全部 16 册 PDF。测试覆盖资料包搬动、各册 PDF 读取、跨页词目标和损坏拒绝。消费端后续已修复并核对管理模式按标签过滤菜单；右键选择后的 PDF 阅读窗口与翻页验收待完成。

## 后续词性扩展

用户询问在索引中补词性及减少重扫的方法。建议由 Codex 依据每条出处的词头和教材释义先补推断词性，歧义项再看已有区域裁图；确认教材 `vt.` / `vi.` 等原文标注需对照实际词表。支持多词性并区分推断与原文来源，保留待核状态。完整建议见 [README 的后续词性补全方案](../../../README.md#后续词性补全方案尚未实施)。现行 v2 尚无词性字段，这一扩展另立实施票。

## 非目标

音标、词性暂不加入正式词源索引；区域图和完整原页保留它们供后续处理。没有用裁剪本身证明识别准确率提高。本票不发布教材扫描件。

## Comments

- 2026-10-08：用户要求先开票。价值在于让查词出处可回到原书核验，尤其能暴露现有人教 OCR 索引错误；本轮只记录需求，不开始裁页、索引或应用实现。
- 2026-10-08：需求梳理补充二次处理资料的保存约定：已核对的区域坐标与页码关系入统一 JSON 映射，裁图和识别候选留在 `_work/`；用户阅读时打开完整原页，保留教材版面与上下文。本轮更新需求，未开始生成资料或修改应用。
- 2026-10-08：用户确认上述需求并要求整理文档、先提交。明确每册一份整页快照、三种页码的区别及待实现的资料路径；本次提交仅包含 #09 需求文档与 README 入口。
- 2026-10-08：用户进一步要求完整重建与随词典打包，并指定由 Codex 自己识别。已停止刚启动的 LM Studio 请求；按最新范围逐页核对、转录与打包，旧的“只重建定位”选择已被替代。

- 2026-10-08：按最新完整重做范围统一票据，建立严格的 v2 索引与可移动资料包；消费端由 #25 承接，原生 Tooltip 保留。
- 2026-10-08：用户要求整理文档后提交当前实现，授权 commit，未授权 push。文档记录已完成的数据/打包/测试和未完成的桌面验收；另记录按词头与释义推断词性的后续方案。
