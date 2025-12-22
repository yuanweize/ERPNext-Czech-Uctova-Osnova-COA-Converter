# ERPNext Czech Účtová Osnova (COA Converter)（中文）

- 作用：将捷克公共部门会计科目表（Směrná účtová osnova）转换为 ERPNext 可导入的多语 CSV（捷克/英语/中文），并处理科目编号冲突、名称长度限制。
- 输入：官方 XML `uctosnova.xml`（示例已附）。
- 输出：`erpnext_coa_multilingual_YYYYMMDD_HHMM.csv`（带时间戳）。
- 翻译：支持 SiliconFlow / OpenRouter / OpenAI / Gemini，IPSAS/CAS 术语优先；支持缓存、重试、离线模式（跳过 API）。

## 快速开始
1) 创建虚拟环境并激活。
2) `pip install -r requirements.txt`
3) 复制 `.env.example` 为 `.env`，设置 `PROVIDER`（siliconflow|openrouter|openai|gemini），填对应 API Key（或使用 `--offline`）。默认不翻译（仅输出捷克语）；如需翻译，设 `TRANSLATE_ENABLED=true` 并指定语言。
4) 运行：
```bash
python erpnext_coa_translator.py
```

## 配置项（.env）
- `PROVIDER` 取值 `siliconflow|openrouter|openai|gemini`
- SiliconFlow: `SILICONFLOW_API_KEY`，`MODEL_ID`（默认 `Qwen/Qwen2.5-72B-Instruct`）
- OpenRouter: `OPENROUTER_API_KEY`，`OPENROUTER_MODEL`（默认 `openai/gpt-4o`）
- OpenAI: `OPENAI_API_KEY`，`OPENAI_MODEL`（默认 `gpt-4o-mini`）
- Gemini: `GEMINI_API_KEY`，`GEMINI_MODEL`（默认 `gemini-1.5-flash`）
- 翻译开关: `TRANSLATE_ENABLED`（默认 false，仅捷克语输出）；`TRANSLATE_LANGS`（默认 `en,zh`，只允许两种两字母语言代码）。示例：`en,zh` -> cz/en/zh；`kr` -> cz/kr；`de,pl` -> cz/de/pl；超过两种将报错。输出文件名会带语言标识，例如 `erpnext_coa_CZ_EN_YYYYMMDD_HHMM.csv`（下划线分隔，兼容 Windows）。
- 运行时：`MAX_WORKERS` / `BATCH_SIZE` / `CURRENCY` / `LIMIT` / `OUTPUT_PREFIX`

## 数据源
- CSV: https://monitor.statnipokladna.gov.cz/data/csv/CIS_POLVYK.CSV
- XML: https://monitor.statnipokladna.gov.cz/data/xml/uctosnova.xml
- XSD: https://monitor.statnipokladna.gov.cz/data/xsd/ciselniky/monitorUctosnova.xsd
- 数据集入口（如链接变动可从此获取最新）：https://data.gov.cz/dataset?iri=https%3A%2F%2Fdata.gov.cz%2Fzdroj%2Fdatov%C3%A9-sady%2F00006947%2F87ab86b58f0a0341acb8cb84ca4094fb

## 其它
- `translation_cache.json` 保留做示例；`translation_cache_Qwen/` 已忽略。
- MIT 许可证，见 LICENSE。

## 项目结构（Tree）
- erpnext_coa_translator.py：主转换与生成脚本
- translation_cache.json：示例缓存（保留）
- CIS_POLVYK.CSV / uctosnova.xml：官方示例数据
- README.md / README.cs.md / README.zh.md：英文/捷克语/中文文档
- requirements.txt：依赖
- .env.example：配置模板
- .gitignore：忽略 venv、缓存、时间戳输出、临时目录
- erpnext_coa_multilingual_YYYYMMDD_HHMM.csv：生成文件（已忽略）
- translation_cache_Qwen/：临时缓存目录（已忽略）
