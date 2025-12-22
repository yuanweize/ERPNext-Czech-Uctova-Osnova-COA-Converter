# ERPNext Czech Účtová Osnova (COA Converter)

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

English | [Čeština](README.cs.md) | [中文](README.zh.md)

Convert the Czech public-sector Chart of Accounts (Směrná účtová osnova) into an ERPNext-ready CSV.

- Input: official `uctosnova.xml`
- Output: importable CSV with correct ERPNext roots and hierarchy
- Optional LLM translation (CZ + up to 2 target languages) with caching and offline mode

## Samples
These are committed examples you can open immediately (no API keys needed):

- [samples/erpnext_coa_CZ_sample.csv](samples/erpnext_coa_CZ_sample.csv) — CZ only
- [samples/erpnext_coa_CZ_EN_sample.csv](samples/erpnext_coa_CZ_EN_sample.csv) — CZ/EN
- [samples/erpnext_coa_CZ_DE_RU_sample.csv](samples/erpnext_coa_CZ_DE_RU_sample.csv) — CZ/DE/RU
- [samples/erpnext_coa_CZ_ZH_RU_sample.csv](samples/erpnext_coa_CZ_ZH_RU_sample.csv) — CZ/ZH/RU

## Quick start
```bash
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements.txt
python erpnext_coa_translator.py --offline
```

To enable translation: copy `.env.example` -> `.env`, set `PROVIDER=...` and the matching API key, then set `TRANSLATE_ENABLED=true`.

## Output naming
Generated files are gitignored and include a timestamp (minute precision):

- Default prefix: `OUTPUT_PREFIX=erpnext_coa_multilingual`
- CZ-only example: `erpnext_coa_multilingual_CZ_YYYYMMDD_HHMM.csv`
- With languages example: `erpnext_coa_multilingual_CZ_EN_ZH_YYYYMMDD_HHMM.csv`

Language tags use underscores for Windows-safe filenames.

## Configuration (.env)
| Variable | Meaning |
|---|---|
| `PROVIDER` | `siliconflow\|openrouter\|openai\|gemini` |
| `SILICONFLOW_API_KEY` / `MODEL_ID` | SiliconFlow key / model |
| `OPENROUTER_API_KEY` / `OPENROUTER_MODEL` | OpenRouter key / model |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | OpenAI key / model |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | Gemini key / model (OpenAI-compatible endpoint) |
| `TRANSLATE_ENABLED` | `true` to add translations (default `false`) |
| `TRANSLATE_LANGS` | Two-letter codes, max 2 (default `en,zh`) |
| `MAX_WORKERS` / `BATCH_SIZE` | Concurrency tuning |
| `CURRENCY` | ERPNext account currency (default `CZK`) |
| `LIMIT` | ERPNext name length limit (default `131`) |
| `OUTPUT_PREFIX` | Output filename prefix |

## Data sources (official)
- CSV: https://monitor.statnipokladna.gov.cz/data/csv/CIS_POLVYK.CSV
- XML: https://monitor.statnipokladna.gov.cz/data/xml/uctosnova.xml
- XSD: https://monitor.statnipokladna.gov.cz/data/xsd/ciselniky/monitorUctosnova.xsd
- Dataset hub: https://data.gov.cz/dataset?iri=https%3A%2F%2Fdata.gov.cz%2Fzdroj%2Fdatov%C3%A9-sady%2F00006947%2F87ab86b58f0a0341acb8cb84ca4094fb

## Tech stack & design
- Python 3.10+, minimal deps (`requests`, `python-dotenv`, optional `tqdm`).
- Provider-agnostic calls via OpenAI-compatible chat APIs.
- Cache + backoff + retry to avoid partial outputs.
- ERPNext-specific shaping: hierarchy, duplicate account numbers, length-safe names.

## License
MIT. See [LICENSE](LICENSE).
