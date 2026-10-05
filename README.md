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

## 远程

- `origin` → 本 fork（`uniquejava/FreePEP`）
- `upstream` → `siknet/FreePEP`

上游功能、WebUI、参数全集仍以 [README.upstream.md](./README.upstream.md) 为准。
