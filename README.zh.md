# ERPNext Czech Účtová Osnova (COA Converter)（中文）

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

将捷克公共部门会计科目表（Směrná účtová osnova）转换为 ERPNext 可直接导入的 CSV。

- 输入：官方 `uctosnova.xml`
- 输出：带层级与根类别（Asset/Liability/Equity/Income/Expense）的 ERPNext CSV
- 可选翻译：捷克语 + 最多 2 种目标语言（带缓存/重试/离线模式）

## 示例文件
以下示例 CSV 已提交到仓库，无需 API Key 也能直接查看：

- [erpnext_coa_CZ_sample.csv](erpnext_coa_CZ_sample.csv) — 仅 CZ
- [erpnext_coa_CZ_EN_sample.csv](erpnext_coa_CZ_EN_sample.csv) — CZ/EN
- [erpnext_coa_CZ_DE_RU_sample.csv](erpnext_coa_CZ_DE_RU_sample.csv) — CZ/DE/RU
- [erpnext_coa_CZ_ZH_RU_sample.csv](erpnext_coa_CZ_ZH_RU_sample.csv) — CZ/ZH/RU

## 快速开始
```bash
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements.txt
python erpnext_coa_translator.py --offline
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
