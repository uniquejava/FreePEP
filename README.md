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
python3 -m vocab_ocr pep --all                 # 缺册才 OCR；--force 重跑
python3 -m vocab_ocr pep --book junior-8a --force  # 单册预览写入 data/vocab/_work/preview/
python3 -m vocab_ocr pep --rebuild-index       # 仅从 books/*.json 重打包
```

人教与新概念共用索引 schema `v: 1`：每条 hit **末尾是中文释义**；同一词在两单元/课出现则两条 hit。词性不进索引。

```json
{
  "v": 1,
  "books": { "junior-8a": "英语八年级上册" },
  "w": {
    "landscape": [["junior-8a", "1", "风景；景色"], ["junior-8a", "8", "风景；景色"]]
  }
}
```

`w[word]` → `[book_id, unit|lesson, zh]`，有页码时为 `[book_id, unit|lesson, page, zh]`。`--book` 只在忽略入库的 `_work/preview/` 生成单册预览，不覆盖正式索引；`--all` 和 `--rebuild-index` 才写全系列索引。`_work/`、分册 `books/*.json` 不入库。空释义与明显 OCR 碎片会被排除；初中目录识别失败时，对已核对页数的本机版本使用目录页单元起始页。OCR 仍有误差，打标前宜抽样。

新概念二册试点不走全书 OCR。输入是本机 Excel（第一个工作表前四列：`单词 / 英音 / 美音 / 释义`）和按 `Lesson N` 分组的课次词表纯文本。默认 Excel 位于 `~/code/English/8.新概念英语/新概念英语第二册（新版）.xlsx`；课次词表默认读取 `data/vocab/_work/nce-2/sohu-lesson-vocab.txt`，缺失时从 [搜狐课次词表](https://www.sohu.com/a/517761822_699921) 获取。可用参数指定本机副本，避免依赖固定目录或在线页面：

```bash
python3 -m vocab_ocr.nce.pilot_nce2_from_excel --xlsx /path/to/新概念英语第二册.xlsx --lesson-vocab /path/to/lesson-vocab.txt
```

产出 [`data/vocab/nce-vocab-index.min.json`](./data/vocab/nce-vocab-index.min.json)（同一 `v: 1`）。三、四册未做。票在 [`.scratch/english-vocab-ocr/`](./.scratch/english-vocab-ocr/)（`#01`）和 [`.scratch/nce-vocab-index/`](./.scratch/nce-vocab-index/)（`#02`）。

---

## 远程

- `origin` → 本 fork（`uniquejava/FreePEP`）
- `upstream` → `siknet/FreePEP`

上游功能、WebUI、参数全集仍以 [README.upstream.md](./README.upstream.md) 为准。
