# ERPNext Czech Účtová Osnova (COA Converter)

English | [Čeština](README.cs.md) | [中文](README.zh.md)

A small utility to convert the Czech public sector Chart of Accounts (Směrná účtová osnova) into an ERPNext-ready multilingual CSV (Czech / English / Chinese). It normalizes source XML, translates with LLMs (SiliconFlow / OpenRouter / OpenAI / Gemini) respecting IPSAS/CAS terminology, handles duplicate account numbers, and stamps output filenames with a timestamp for auditing.

## Key features
- ERPNext-focused mapping of Czech COA to Asset/Liability/Equity/Income/Expense roots.
- Multilingual names (CZ / EN / ZH) with smart length fitting for ERPNext limits.
- Caching + retry with exponential backoff; optional offline mode (skip API, use cache/original CZ).
- Timestamped outputs: `erpnext_coa_multilingual_YYYYMMDD_HHMM.csv`.

## Samples
- [erpnext_coa_CZ_sample.csv](erpnext_coa_CZ_sample.csv) — CZ only
- [erpnext_coa_CZ_EN_sample.csv](erpnext_coa_CZ_EN_sample.csv) — CZ/EN
- [erpnext_coa_CZ_DE_RU_sample.csv](erpnext_coa_CZ_DE_RU_sample.csv) — CZ/DE/RU (example of two extra languages)
- [erpnext_coa_CZ_ZH_RU_sample.csv](erpnext_coa_CZ_ZH_RU_sample.csv) — CZ/ZH/RU

## Data sources (official)
- CSV: https://monitor.statnipokladna.gov.cz/data/csv/CIS_POLVYK.CSV
- XML: https://monitor.statnipokladna.gov.cz/data/xml/uctosnova.xml
- XSD: https://monitor.statnipokladna.gov.cz/data/xsd/ciselniky/monitorUctosnova.xsd
- Dataset hub (latest links): https://data.gov.cz/dataset?iri=https%3A%2F%2Fdata.gov.cz%2Fzdroj%2Fdatov%C3%A9-sady%2F00006947%2F87ab86b58f0a0341acb8cb84ca4094fb

## Quick start
1) Python 3.10+ and git clone.
2) `python -m venv .venv && .venv/Scripts/activate` (Windows) or `source .venv/bin/activate` (Unix).
3) `pip install -r requirements.txt`.
4) Copy `.env.example` -> `.env`, choose provider (`PROVIDER=siliconflow|openrouter|openai|gemini`), fill the corresponding API key. Translation is off by default (Czech-only); set `TRANSLATE_ENABLED=true` to emit CZ plus your target languages.

### Offline / full run (uses cache or translates missing terms if API key present):
```bash
python erpnext_coa_translator.py
```
- Uses `uctosnova.xml` as input.
- Writes `erpnext_coa_multilingual_YYYYMMDD_HHMM.csv`.
- Caches translations in `translation_cache.json` (kept in repo for baseline examples).

## Configuration (.env)
- `PROVIDER` one of `siliconflow|openrouter|openai|gemini`
- SiliconFlow: `SILICONFLOW_API_KEY`, `MODEL_ID` (default `Qwen/Qwen2.5-72B-Instruct`)
- OpenRouter: `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` (default `openai/gpt-4o`)
- OpenAI: `OPENAI_API_KEY`, `OPENAI_MODEL` (default `gpt-4o-mini`)
- Gemini: `GEMINI_API_KEY`, `GEMINI_MODEL` (default `gemini-1.5-flash`), via OpenAI-compatible endpoint
- Translation: `TRANSLATE_ENABLED` (default `false` for CZ-only output); `TRANSLATE_LANGS` (default `en,zh`, two-letter codes, max 2). Examples: `en,zh` -> cz/en/zh; `kr` -> cz/kr; `de,pl` -> cz/de/pl. More than 2 codes errors. Output filenames include language tags, e.g., `erpnext_coa_CZ_EN_YYYYMMDD_HHMM.csv` (underscore for Windows-safe names).
- Runtime: `MAX_WORKERS`, `BATCH_SIZE`, `CURRENCY`, `LIMIT`, `OUTPUT_PREFIX`

## Keywords
ERPNext chart of accounts, COA, Czech accounting, Směrná účtová osnova, IPSAS mapping, CAS/ASBE, multilingual CSV export, XML to CSV converter, Czech public sector finance.

## License
MIT. See [LICENSE](LICENSE).

## Notes
- `translation_cache_Qwen/` is ignored (scratch). Keep `translation_cache.json` as sample cache.
- Example data `CIS_POLVYK.CSV` and `uctosnova.xml` are retained for reproducible demos.
- Output files are timestamped; add preferred sample to docs if needed.

## Tech stack & design
- Python 3.10+, `requests`, `dotenv`, `tqdm`, stdlib only; OpenAI-compatible chat APIs for all providers.
- Prompting: JSON-only responses, IPSAS/CAS terminology guardrails, two-language cap to keep outputs predictable.
- Resilience: caching + exponential backoff + retry on missing terms; offline mode falls back to CZ/cache.
- Data shaping: Czech term normalization, duplicate account number resolution, length-safe naming for ERPNext.
- Outputs: Windows-safe language-tagged filenames, configurable currency/limits, timestamped CSV for audit.

## Project structure (tree)
- erpnext_coa_translator.py — main translator/generator
- translation_cache.json — sample cache kept in repo
- CIS_POLVYK.CSV / uctosnova.xml — official sample data inputs
- README.md / README.cs.md / README.zh.md — docs (EN/CZ/ZH)
- requirements.txt — runtime deps
- .env.example — config template
- .gitignore — ignores venv, caches, timestamped outputs, scratch folder
- erpnext_coa_multilingual_YYYYMMDD_HHMM.csv — generated output (gitignored)
- translation_cache_Qwen/ — scratch cache (gitignored)
