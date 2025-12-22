# ERPNext Czech Účtová Osnova (COA Converter)

English | [Čeština](README.cs.md) | [中文](README.zh.md)

A small utility to convert the Czech public sector Chart of Accounts (Směrná účtová osnova) into an ERPNext-ready multilingual CSV (Czech / English / Chinese). It normalizes source XML, translates with SiliconFlow (Qwen) respecting IPSAS/CAS terminology, handles duplicate account numbers, and stamps output filenames with a timestamp for auditing.

## Key features
- ERPNext-focused mapping of Czech COA to Asset/Liability/Equity/Income/Expense roots.
- Multilingual names (CZ / EN / ZH) with smart length fitting for ERPNext limits.
- Caching + retry with exponential backoff; optional offline mode (skip API, use cache/original CZ).
- Timestamped outputs: `erpnext_coa_multilingual_YYYYMMDD_HHMM.csv`.

## Data sources (official)
- CSV: https://monitor.statnipokladna.gov.cz/data/csv/CIS_POLVYK.CSV
- XML: https://monitor.statnipokladna.gov.cz/data/xml/uctosnova.xml
- XSD: https://monitor.statnipokladna.gov.cz/data/xsd/ciselniky/monitorUctosnova.xsd

## Quick start
1) Python 3.10+ and git clone.
2) `python -m venv .venv && .venv/Scripts/activate` (Windows) or `source .venv/bin/activate` (Unix).
3) `pip install -r requirements.txt`.
4) Copy `.env.example` -> `.env`, fill `SILICONFLOW_API_KEY` (or run offline for demos).

### Offline / full run (uses cache or translates missing terms if API key present):
```bash
python erpnext_coa_translator.py
```
- Uses `uctosnova.xml` as input.
- Writes `erpnext_coa_multilingual_YYYYMMDD_HHMM.csv`.
- Caches translations in `translation_cache.json` (kept in repo for baseline examples).

## Configuration (.env)
- `SILICONFLOW_API_KEY` (required for translation)
- `MODEL_ID` (default `Qwen/Qwen2.5-72B-Instruct`)
- `MAX_WORKERS`, `BATCH_SIZE` (concurrency)
- `CURRENCY` (default CZK)
- `LIMIT` (ERPNext name length limit, default 131)
- `OUTPUT_PREFIX` (default `erpnext_coa_multilingual`)

## SEO / Keywords
ERPNext chart of accounts, Czech accounting, Směrná účtová osnova, IPSAS mapping, CAS/ASBE, multilingual CSV export, XML to CSV converter, Czech public sector finance.

## License
MIT. See [LICENSE](LICENSE).

## Notes
- `translation_cache_Qwen/` is ignored (scratch). Keep `translation_cache.json` as sample cache.
- Example data `CIS_POLVYK.CSV` and `uctosnova.xml` are retained for reproducible demos.
- Output files are timestamped; add preferred sample to docs if needed.
