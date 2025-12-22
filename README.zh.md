# ERPNext Czech Účtová Osnova (COA Converter)（中文）

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

[English](README.md) | [Čeština](README.cs.md) | 中文

将捷克公共部门会计科目表（Směrná účtová osnova）转换为 ERPNext 可直接导入的 CSV。

- 输入：官方 `uctosnova.xml` 或 `CIS_POLVYK.CSV`（文件名不限制；服务端/CLI 都按内容校验格式）
- 输出：带层级与根类别（Asset/Liability/Equity/Income/Expense）的 ERPNext CSV
- 可选翻译：捷克语 + 最多 2 种目标语言（带缓存/重试/离线模式）

## 示例文件
以下示例 CSV 已提交到仓库，无需 API Key 也能直接查看：

- [samples/erpnext_coa_CZ_sample.csv](samples/erpnext_coa_CZ_sample.csv) — 仅 CZ
- [samples/erpnext_coa_CZ_EN_sample.csv](samples/erpnext_coa_CZ_EN_sample.csv) — CZ/EN
- [samples/erpnext_coa_CZ_DE_RU_sample.csv](samples/erpnext_coa_CZ_DE_RU_sample.csv) — CZ/DE/RU
- [samples/erpnext_coa_CZ_ZH_RU_sample.csv](samples/erpnext_coa_CZ_ZH_RU_sample.csv) — CZ/ZH/RU


## Web UI（本地 / 服务器）

本仓库已内置单页 Web UI：拖拽上传（支持 `uctosnova.xml` 和 `CIS_POLVYK.CSV`）、FIFO 队列、SSE 实时进度、处理完成后直接下载 ERPNext CSV。

![Web UI 页面截图](https://github.com/user-attachments/assets/bd357431-8886-494e-919f-ab248fed833f)

- 本地运行：
	- `pip install -r requirements.txt`
	- `uvicorn web.server:app --reload`
	- 打开 `http://127.0.0.1:8000`

- 一键部署（完整服务，含 Python 后端）：
	- [![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/yuanweize/ERPNext-Czech-Uctova-Osnova-COA-Converter)

说明：
- Cloudflare Pages / EdgeOne / Vercel / Netlify 主要是“静态托管”，不适合直接运行本项目的 Python 转换后端（无法做到同一个站点里完成“上传→处理→下载”）。

更多可部署（Docker / Python 后端）平台（都能跑本仓库的 Dockerfile）：
- Render（按钮最省事）：上面的 Deploy to Render
- [![Deploy to Railway](https://img.shields.io/badge/Deploy%20to-Railway-0B0D0E?logo=railway&logoColor=white)](https://railway.app/new)
- [![Deploy to Koyeb](https://img.shields.io/badge/Deploy%20to-Koyeb-121212?logo=koyeb&logoColor=white)](https://app.koyeb.com/)
- [![Deploy to Fly.io](https://img.shields.io/badge/Deploy%20to-Fly.io-7B5CFF?logo=flydotio&logoColor=white)](https://fly.io/)

说明：Railway/Koyeb/Fly.io 通常需要在它们的控制台里点几步选择“从 GitHub 导入 + Docker 构建”，它们没有像 Render/Vercel/Netlify 那种“带 repo 参数的一键 clone 按钮链接”统一标准（所以这里提供的是“直达创建入口”的按钮）。

如果你希望 Cloudflare Pages / EdgeOne 也能用：可以把前端静态页部署在 CF/EO，后端单独部署在 Render/Railway，然后前端加一个“Backend URL”配置指向后端（我也可以继续把这一点做成 UI 可配置）。

## 项目结构（Project Tree）

```text
.
├─ erpnext_coa_translator.py        # 命令行转换器：XML/CSV -> ERPNext COA CSV（可选翻译）
├─ web/
│  ├─ server.py                    # FastAPI 后端：FIFO 任务队列、SSE 进度、下载接口
│  └─ static/
│     └─ index.html                # 单页前端（拖拽上传、队列、进度、下载）
├─ samples/                        # 仓库内置示例输出（可直接打开）
├─ requirements.txt                # Python 依赖（CLI + Web）
├─ Dockerfile                      # Docker 运行入口（uvicorn）
├─ render.yaml                     # Render 部署蓝图
├─ uctosnova.xml                   # 官方 XML 输入（可选）
├─ CIS_POLVYK.CSV                  # 官方 CSV 输入（可选）
├─ translation_cache.json          # 翻译缓存（CLI 使用；可重新生成）
└─ README*.md                      # 文档（EN/CZ/ZH）
```

## 安全说明（重点）

- 不限制文件名：你上传的文件可以叫任何名字。服务端会按内容识别并校验格式：XML 必须包含 `<row>` 且具备关键字段；CSV 必须符合 CIS_POLVYK 的表头结构；否则直接返回“解析错误”。
- API Key：Web UI 只在你的浏览器本地保存（localStorage），提交任务时随请求发送；服务端不落盘保存，并在任务启动后清空内存中的 API Key。
- 防滥用/限流：可用环境变量控制 `MAX_UPLOAD_MB`（上传大小）、`MAX_QUEUE`（队列长度）、`MAX_JOBS`（内存任务数）、`JOB_TTL_SECONDS`（完成任务保留时间）。
- 若你曾经把真实 API Key 提交到 Git 历史，请立刻在供应商后台撤销/轮换。

## 快速开始
```bash
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements.txt
python erpnext_coa_translator.py --input uctosnova.xml --offline
# 或：python erpnext_coa_translator.py --input CIS_POLVYK.CSV --offline
# CLI 会按内容自动识别 XML/CSV（文件名/扩展名不重要）。
```

如需启用翻译：复制 `.env.example` 为 `.env`，设置 `PROVIDER=...` 并填写对应 API Key，然后设置 `TRANSLATE_ENABLED=true`。

## 输出文件命名
生成文件默认会被 gitignore 忽略，并包含时间戳（精确到分钟）：

- 默认前缀：`OUTPUT_PREFIX=erpnext_coa_multilingual`
- 仅 CZ 示例：`erpnext_coa_multilingual_CZ_YYYYMMDD_HHMM.csv`
- 多语言示例：`erpnext_coa_multilingual_CZ_EN_ZH_YYYYMMDD_HHMM.csv`

语言标签用下划线分隔，保证 Windows 文件名兼容。

## 配置项（.env）
| 变量 | 说明 |
|---|---|
| `PROVIDER` | `siliconflow\|openrouter\|openai\|gemini` |
| `SILICONFLOW_API_KEY` / `MODEL_ID` | SiliconFlow key / 模型 |
| `OPENROUTER_API_KEY` / `OPENROUTER_MODEL` | OpenRouter key / 模型 |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | OpenAI key / 模型 |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | Gemini key / 模型（OpenAI 兼容端点） |
| `TRANSLATE_ENABLED` | `true` 开启翻译（默认 `false`） |
| `TRANSLATE_LANGS` | 两字母语言代码，最多 2 个（默认 `en,zh`） |
| `MAX_WORKERS` / `BATCH_SIZE` | 并发与分批 |
| `CURRENCY` | ERPNext 币种（默认 `CZK`） |
| `LIMIT` | ERPNext 名称长度上限（默认 `131`） |
| `OUTPUT_PREFIX` | 输出文件名前缀 |

## 数据源（官方）
- CSV: https://monitor.statnipokladna.gov.cz/data/csv/CIS_POLVYK.CSV
- XML: https://monitor.statnipokladna.gov.cz/data/xml/uctosnova.xml
- XSD: https://monitor.statnipokladna.gov.cz/data/xsd/ciselniky/monitorUctosnova.xsd
- 数据集入口: https://data.gov.cz/dataset?iri=https%3A%2F%2Fdata.gov.cz%2Fzdroj%2Fdatov%C3%A9-sady%2F00006947%2F87ab86b58f0a0341acb8cb84ca4094fb

## 技术栈与设计
- Python 3.10+，轻量依赖（`requests`、`python-dotenv`，可选 `tqdm`）。
- 通过 OpenAI 兼容聊天接口统一接入多家提供商。
- 缓存 + 指数退避 + 缺失项重试，避免生成“半成品”。
- 针对 ERPNext：保持层级结构、解决科目号冲突、名称长度自适应。

## 许可证
MIT，见 LICENSE。
