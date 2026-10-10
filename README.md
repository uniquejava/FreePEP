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

现行流程由 **Codex 与获授权的子代理直接查看原书图片、逐页转录**，脚本仅渲染、存储、校验和打包，不调用本地模型。覆盖人教版 13 册与经典版新概念 4 册，共 17 本；九年级采用新版上下册，替换旧全一册，见 [#12](./.scratch/junior9-new-edition/issues/01-replace-grade9-index.md)。完整实施约定见 [#09](./.scratch/vocab-page-links/issues/01-vocab-page-pdf-links.md)，人教质量重建承接 [#05](./.scratch/english-vocab-ocr/issues/05-pep-visual-index-rebuild.md)，词典消费端为 [EggplantDict #25](../eggplant-projects/EggplantDict/.scratch/mvp/issues/25-textbook-reference-bundle.md)。

### 正式数据与原页资料包

两套索引共用 **`v:2`** 对象结构：

- [`data/vocab/vocab-index.min.json`](./data/vocab/vocab-index.min.json)：人教版词头、课次、完整教材中文释义和原页；九下难辨中文的辅助来源按 `gloss_version:1` 明确标记。
- [`data/vocab/nce-vocab-index.min.json`](./data/vocab/nce-vocab-index.min.json)：新概念四册，以原书词表重新转录，替代旧 Excel 词头与空释义；保留同词多课。
- [`data/vocab/vocab-page-map.json`](./data/vocab/vocab-page-map.json)：源书校验值、三种页码、真实初中目录单元边界、区域框和阅读顺序。
- `downloads/vocab-reference/`：可移动的完整资料包，两份索引、映射、校验清单与 `pdf/<book_id>-vocab.pdf`。**每册一份 PDF，汇集该册全部完整词表页，17 册共 17 份、545 页。** 九上20页；九下11页采用带说明的中文清晰阅读衍生页，原书身份仍绑定108页候选。原书与快照不入 Git。

```json
{
  "v": 2,
  "books": {"senior-optional-3": "英语选择性必修第三册"},
  "pdfs": {"senior-optional-3": {
    "file": "pdf/senior-optional-3-vocab.pdf", "sha256": "…", "page_count": 13
  }},
  "w": {"nuclear": [{
    "book": "senior-optional-3", "unit": "3", "zh": "原子能的；核能的；原子核的", "headword": "nuclear",
    "pdf_pages": [3, 4],
    "references": [{"pdf_page": 3, "region_id": "right"}, {"pdf_page": 4, "region_id": "left"}]
  }]}
}
```

`pdf_pages` 是抽页后 PDF 的 **1 起始页序**；映射另外保存源 PDF 页序与印刷页码。初中命中的可选 `page` 是词表打印的正文引用页，不能当作词表 PDF 页。教材印刷词性由下述 `pos_version:1` 扩展保存；音标继续保留在完整书页。同词多册、多课次、不同教材释义、单元表/A–Z 重复印刷和跨页均保留关系；打印的其他拼法/缩写可作为查询别名。七上参考词表没有课次的词使用 `reference`，不猜 Unit。

### 复跑与打包

用 `python3 -m venv .venv` 建立环境，再运行 `.venv/bin/python -m pip install -r requirements.txt`；渲染/裁图需要 `brew install poppler`。

```bash
.venv/bin/python -m vocab_ocr.reference prepare-grade9 \
  --work data/vocab/_work/junior9-index \
  --base-work data/vocab/_work/reference-rebuild \
  --base-bundle downloads/vocab-reference-before-grade9 \
  --reading-pdf 'downloads/初中（六三学制）/九年级/英语九年级下册-词表中文清晰版.pdf'
.venv/bin/python -m vocab_ocr.reference status --work data/vocab/_work/junior9-index
.venv/bin/python -m vocab_ocr.reference build \
  --work data/vocab/_work/junior9-index \
  --base-bundle downloads/vocab-reference-before-grade9 \
  --output downloads/vocab-reference
.venv/bin/python -m vocab_ocr.reference validate --output downloads/vocab-reference
.venv/bin/python -m vocab_ocr.reference publish --output downloads/vocab-reference
.venv/bin/python -m vocab_ocr.reference install \
  --destination ../eggplant-projects/EggplantDict/EggplantDict/Resources/TextbookReferences
```

逐页证据保留在被 Git 忽略的本机工作区：旧15册记录仍在 `data/vocab/_work/reference-rebuild/`，新九年级在 `data/vocab/_work/junior9-index/` 的 `sources.json` 与 `books/<book_id>/pages/`。记录绑定源书 SHA-256，并标记 `codex-direct-vision`。旧完整基准包保存在 `downloads/vocab-reference-before-grade9/`，仅用于冻结数据复用；现行默认包是 `downloads/vocab-reference/`。新版增量构建只消费九上／九下新记录，其他15册命中、映射和PDF原样复用，新概念JSON原字节复制。`build` 要求全部候选页已转录/分类，原书与页数未变，词条/课次/区域/页码有效；失败不覆盖已发布的资料包。`install` 校验后整体替换消费端资源目录。应用构建把完整目录复制到 `.app/Contents/Resources/TextbookReferences/`，运行时不依赖 FreePEP、原书路径或工作缓存；资料不完整或版本不符时拒绝打开。

人教源书由 [`vocab_ocr/pep/catalog.py`](./vocab_ocr/pep/catalog.py) 定位。新概念默认源书在 `~/Pdf/新概念课文1-4PDF/`，必须使用完整四册；第四册是 `新概念4-完整.pdf`，同目录 49 页的 `新概念4.pdf` 不是该完整扫描版。新概念原书目录/续页计划见 [`vocab_ocr/nce/vocab_page_map.json`](./vocab_ocr/nce/vocab_page_map.json)。

本机只保留这一份现行完整包；原书、九下清晰阅读版和 `before-grade9` 冻结基准分别承担来源、修复输入及增量复跑用途。重复生成包、已完成审阅的九年级草稿包与修复预览PDF已清理。逐页转录、修复标注及冻结区域证据保留；需要再次审阅时按下方命令重建草稿。

### 二次处理

```bash
.venv/bin/python -m vocab_ocr.reference regions --book junior-9a --book junior-9b --dpi 200
```

从完整资料包导出 `data/vocab/_work/vocab-page-regions/<book_id>/<快照页>-<region_id>.png`，每张配同名 JSON，记录原页/快照页、区域框、源书与 PDF 校验值、映射校验值、渲染 DPI。坐标为**可见页方向、左上角原点的归一化坐标**，渲染遵循 CropBox 与 PDF 旋转。大部分双栏分开裁；同页跨栏释义用两栏并集区域，跨页词关联全部需要的完整页。后续识别信息应引用这些来源 JSON；裁图可重建，不随应用打包。用户阅读时通过词典标签右键菜单打开**完整原页**，保留书页的感觉；悬停 Tooltip 继续显示书名和课次。

### 九年级增量复核与辅助中文（#12）

新ID为 `junior-9a`、`junior-9b`，现行包及APP不含 `junior-9`。单元边界按该版目录核实：九上8 Unit、九下5 Unit。上册117–136共20页词表；下册94–104共11页。所有候选尾页均直接查看并分类，未把不规则动词、后记或封底当词表。

[EggplantDict #56](../eggplant-projects/EggplantDict/.scratch/mvp/issues/56-grade9-new-edition-resources.md)已完成正式接入：52项Release定向测试与上下册出处、来源说明、待核词性、异常页码和完整阅读页的核心界面验收通过，正常词库已恢复到唯一Release实例。7,057个教材联想键及新版候选由测试确认；当前微信拼音输入法下自动输入未确认候选浮层，实际输入交互留待用户体验。生成端96项测试与9个子测试通过，其余15册资料保持不变。

新册先生成可审阅草稿，再按册导出区域，完成直接视觉复核并将区域JSON／PNG摘要写入每页 `pos_review` 后才正式构建：

```bash
.venv/bin/python -m vocab_ocr.reference draft \
  --work data/vocab/_work/junior9-index --output data/vocab/_work/junior9-index/draft \
  --book junior-9a --book junior-9b
.venv/bin/python -m vocab_ocr.reference regions \
  --work data/vocab/_work/junior9-index --output data/vocab/_work/junior9-index/draft \
  --book junior-9a --book junior-9b --dpi 200
```

草稿带 `kind:draft`，正式校验、发布与安装均拒绝它。重新裁图后须重核并更新对应的证据摘要；不能保留旧证据假称已复核。旧册不重裁。正式构建与已审阅草稿共用同一抽页逻辑，两册PDF字节保持一致。旧全一册源计划不能再正式build；含退役ID的包不能publish/install，旧基准只允许校验与增量复用，防止默认命令覆回旧数据。

人教索引增加 `gloss_version:1`，有辅助中文的命中保存 `gloss_source`。未带字段的记录沿用原印释义；带字段时，释义与 `pos.senses[].zh` 一并保留来源。定义合并身份包含来源，词典显示说明。校验实现见 [gloss.py](./vocab_ocr/gloss.py)。

```json
{"gloss_source":{"status":"supplemented","note":"原页中文难辨，采用同版辅助资料补齐。",
  "sources":[{"kind":"same-edition","label":"同版教学资料","url":"https://zy.21cnjy.com/26012639"}]}}
```

`status`为`cross-reference`（同书另一词表恢复）或`supplemented`（同版／常规专名补齐）。每个来源带`label`；`same-book`记录`source_pdf_pages`，`same-edition`记录HTTP(S) URL，`conventional-name`说明未获独立同版印刷中文确证。索引中26个不同出处有来源标记，包含跨页中文拼接；不能把这些释义称作无标记的逐字原印。

6处正文页码与单元范围／另一词表冲突，保留实际印刷`page`，以`unit_source_pdf_page`与`reference_note`绑定同书另一词项确认Unit：shrimp、bother、postman、trap首义、empty、translate。只有相同词头与Unit的直接引用词项才能确认例外，不接受单纯说明绕过目录校验。

九下的工作计划显式绑定 `reading_derivative`（本机路径、摘要、原书摘要、94–104页序与说明）。公开映射去除本机路径；索引`pdfs[junior-9b].pdf_note`保留阅读衍生用途元数据，APP不再常驻显示这段技术说明。逐释义的辅助中文来源仍显示。英文、音标、词性及页码保留原图，不表示原图疑点已校正；原书身份和英文词性证据仍绑定源书。

### 九下词表中文阅读修复（#13）

用户下载的九下候选词表有中文重影。[#13](./.scratch/junior9-new-edition/issues/02-verify-and-clarify-lower-vocab.md) 另做 11 页阅读衍生 PDF，仅覆盖中文区域，保留英文、音标、词性、词序、正文引用页和印刷页码。难辨处参考同版资料，替补与原页恢复分别记在本机标注的 `origin` / `evidence` 中；该文件不能替代出版社原页或直接发布为正式索引证据。

用户反馈后的续修移除源94／100页（印刷88／94页）顶部仍重影的中文注释，记录为两处 `layout-cleanup`，原有514处词条中文覆盖保持不变。整页像素对比仅这两条注释区域变化；重新打包时阅读衍生绑定及九下区域证据摘要同步更新，不改变词项与其他16册资料。

```bash
.venv/bin/python -m vocab_ocr.clarify_grade9_pdf \
  'downloads/初中（六三学制）/九年级/2027春人教版九年级英语下册电子课本（彩色版）.pdf' \
  data/vocab/_work/junior9-clarity/overlays-094-095.json \
  data/vocab/_work/junior9-clarity/overlays-096-099.json \
  data/vocab/_work/junior9-clarity/overlays-100-104.json \
  --output 'downloads/初中（六三学制）/九年级/英语九年级下册-词表中文清晰版.pdf'
```

标注绑定 `source_sha256`；框、基线和字号采用对应渲染图左上角像素坐标。默认使用 macOS 的宋体 SC（`Songti.ttc`、子字体 6）；其他环境通过 `--font` / `--font-index` 指定已核验字体。生成器转换非零 CropBox 原点，检查页范围、重复页、来源、文字宽度和原书摘要，拒绝覆盖原书，并将逐项依据作为 `chinese-repair-provenance.json` 附件嵌入 PDF。复跑后仍须逐页渲染检查遮罩和文字；原书、标注、渲染图及衍生 PDF 都保留本机，不入 Git。

### 教材印刷词性（#10）

[FreePEP #10](./.scratch/vocab-pos/issues/01-printed-pos-from-regions.md) 与 [EggplantDict #26](../eggplant-projects/EggplantDict/.scratch/mvp/issues/26-textbook-printed-pos.md) 承接现成区域图的直接视觉识读。#10初次发布的16册共14,438条：11,983条带印刷词性、2,409条未标注、46条类型说明，待核/推断均为0；历史明细见#10。#12替换后，九上922条为750印刷／172未标；九下456条为353印刷／91未标／12待核，均完成原页和区域复核。待核条目保留原字及说明，不用通用语法覆盖。脚本不做 OCR 或调用识别模型。

扩展保持 `v:2`，完整识读索引增加 `pos_version:1`。每条出处的可选 `pos` 包含 `status`、教材原文 `raw` 和规范 `tags` 列表；旧 v2 无这些字段仍可读取。多项原文标签按印刷顺序以分号或换行连接，组合标注保留 `&`。词性属于该条教材释义，不能给整个查询词头套一个通用词性。

```json
{
  "pos": {"status": "printed", "raw": "n.; adv.", "tags": ["noun", "adverb"],
    "senses": [{"raw": "n.", "tags": ["noun"], "zh": "家"},
               {"raw": "adv.", "tags": ["adverb"], "zh": "在家，到家"}]},
  "pos_evidence": [{"pdf_page": 1, "source_pdf_page": 10, "region_id": "words",
    "source_sha256": "…", "metadata_sha256": "…", "image_sha256": "…"}]
}
```

`status` 分为 `printed`（直接看到的教材词性）、`unmarked`（没有词性，raw/tags 空）、`type`（如 `abbr.`、`question word`，保留说明但 tags 空）、`unresolved`（待核，note 必填且不声称规范词性）和 `inferred`（推断，raw 空、tags 与 note 必填）。`senses` 只记录原书分别印出的词性与释义段，不凭中文分号猜分义；单组 `vt. & vi.` 对应同段释义时无需拆分。

规范标签为 `noun`、`verb`、`transitive_verb`、`intransitive_verb`、`adjective`、`adverb`、`pronoun`、`preposition`、`conjunction`、`interjection`、`article`、`numeral`、`determiner`、`auxiliary_verb`、`modal_verb`。`vt.`/`vi.` 保留细分，不额外塞入通用 `verb`；`modal v.`/`modal verb` 归为 `modal_verb`，`aux v.` 归为 `auxiliary_verb`，`possessive adjective`/`predicative adj.` 归为 `adjective`，`det.`/`quantifier` 归为 `determiner`，原文均完整保留。规范器见 [`pos.py`](./vocab_ocr/pos.py)。

本机逐页记录新增 `pos_review`，绑定已看区域的来源 JSON 与 PNG 摘要。续页确实未再印词性时，`inherited_from` 精确指定同词、同释义、同课次的实际印出条目，生成器校验并把实际印出区域作为证据。正式 `pos_evidence` 引用完整资料包的原页/区域，页码映射保留对应摘要；图片和本机记录不随应用打包。已复核的 PNG 与来源 JSON 是冻结证据；`regions` 会重建并覆盖它们，改变摘要后必须重新复核并同步逐页 `pos_review`，再执行完整 build/validate，不能沿用旧证据发布。原文、状态、规范词性或分义关系不一致的出处分开保存，别名继承对应出处信息。

`reference status` 按册报告 total/reviewed/pending、各状态和冲突数量。冲突计数比较同词、课次、正文引用页在不同印刷页的状态/规范词性集合，同页分义不计为重复印刷冲突；原文顺序或分义排版不同仍保留独立命中，但不计为语法冲突。只要开始补词性，`build` 就要求全语料每条都有状态并验证来源，不能把单册预览覆盖正式索引。带 `pos_version:1` 却缺状态、印字与规范标签不符、区域证据错页或摘要不一致都会拒绝发布/载入。生成、发布和安装仍使用上面的完整命令。消费端只保存和校验教材属性，原生 Tooltip、标签菜单与完整原页阅读沿用 #25。

这次处理补充现有词项属性，不代表重新完成漏词覆盖检查；发现原转录错误需另列并保留原页依据。

### 质量与历史流程

逐页重新识读共检查 728 张候选页，收录 542 张词表页（人教 212、新概念 330），排除 186 张非词表页；记录 14,438 条印刷词项/续页关系。这不是去重后的单词数量。人教的单元表与 A–Z 表分别识读，再比较词项，专名和参考词表保留。九年级目录确认为 **14 个 Unit**，修正旧回退映射漏掉 Unit 13、14 的问题。原书本身的印字/单元号冲突按各处实际内容保留，可回原页核验。

[#04](./.scratch/english-vocab-ocr/issues/04-pep-index-spot-check.md) 的 60 条旧随机/风险候选已在重建中复核，串栏词头、错误 Unit/页码和串接释义已改为原书真实词项；该样本不能用于估计总体错误率。旧抽检 CSV 留在本机 `_work/pep-audit-sample.csv`，不覆盖其历史判定。

**验收状态（2026-10-08）**：生成端 83 项测试、词典端 194 项测试通过，Release 构建包含完整资料包且校验通过。542 张抽页的内容流、页面边界和旋转与源页一致。标签右键菜单按当前标签过滤已完成检查；右键选择后的 PDF 阅读窗口与翻页仍待桌面验收，见 #09 / 消费端 #25。

旧 Tesseract、LM Studio 实验和 Excel 导入保留用于历史诊断，**不用于现行重建**。`python3 -m vocab_ocr pep --all` / `--book` / `--rebuild-index` 只写 `_work/` 预览。旧 `python3 -m vocab_ocr.nce.build_book_index` 默认写 `_work/nce-legacy-preview/`，旧发布器拒绝降级覆盖 v2。历史 Excel 来源、许可与课次对齐笔记见 [新概念相关票据](./.scratch/nce-vocab-index/)；新正式词头与教材释义来自完整原书图片，不沿用旧 Excel 通用释义。原页 PDF、裁图、原 Excel、`_work/` 与分册缓存均不入 Git。

---

## 远程

- `origin` → 本 fork（`uniquejava/FreePEP`）
- `upstream` → `siknet/FreePEP`

上游功能、WebUI、参数全集仍以 [README.upstream.md](./README.upstream.md) 为准。
