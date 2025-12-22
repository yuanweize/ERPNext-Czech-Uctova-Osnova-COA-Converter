# ERPNext Czech Účtová Osnova (COA Converter)

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

English | [Čeština](README.cs.md) | [中文](README.zh.md)

Convert the Czech public-sector Chart of Accounts (Směrná účtová osnova) into an ERPNext-ready CSV.

- Input: official `uctosnova.xml` or `CIS_POLVYK.CSV` (filename does not matter; format is validated by content)
- Output: importable CSV with correct ERPNext roots and hierarchy
- Optional LLM translation (CZ + up to 2 target languages) with caching and offline mode

## Samples
These are committed examples you can open immediately (no API keys needed):

- [samples/erpnext_coa_CZ_sample.csv](samples/erpnext_coa_CZ_sample.csv) — CZ only
- [samples/erpnext_coa_CZ_EN_sample.csv](samples/erpnext_coa_CZ_EN_sample.csv) — CZ/EN
- [samples/erpnext_coa_CZ_DE_RU_sample.csv](samples/erpnext_coa_CZ_DE_RU_sample.csv) — CZ/DE/RU
- [samples/erpnext_coa_CZ_ZH_RU_sample.csv](samples/erpnext_coa_CZ_ZH_RU_sample.csv) — CZ/ZH/RU

## Web UI (Localhost / Server)

This repo includes a single-page web UI with drag & drop upload (supports `uctosnova.xml` and `CIS_POLVYK.CSV`), FIFO job queue, live progress (SSE), and a downloadable ERPNext CSV.

![Web UI Screenshot](https://github.com/user-attachments/assets/bd357431-8886-494e-919f-ab248fed833f)

- Run locally:
	- `pip install -r requirements.txt`
	- `uvicorn web.server:app --reload`
	- Open `http://127.0.0.1:8000`

- Run with Docker:
	- Build: `docker build -t erpnext-coa .`
	- Run: `docker run --rm -p 8000:8000 erpnext-coa`
	- Open `http://127.0.0.1:8000`
	- If you need translation providers, pass env vars (for example `--env-file .env`).

- Run with Docker Compose:
	- `docker compose up --build`
	- Open `http://127.0.0.1:8000`

- Deploy (full stack, Python backend included):
	- [![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/yuanweize/ERPNext-Czech-Uctova-Osnova-COA-Converter)

Notes:
- Cloudflare Pages / EdgeOne / Vercel / Netlify are mostly static hosting, so they can’t directly run this Python backend (no single-service “upload -> process -> download”).

More deploy options (Docker / Python backend capable):
- Render (fastest): use the “Deploy to Render” button above
- [![Deploy to Railway](https://img.shields.io/badge/Deploy%20to-Railway-0B0D0E?logo=railway&logoColor=white)](https://railway.app/new)
- [![Deploy to Koyeb](https://img.shields.io/badge/Deploy%20to-Koyeb-121212?logo=koyeb&logoColor=white)](https://app.koyeb.com/)
- [![Deploy to Fly.io](https://img.shields.io/badge/Deploy%20to-Fly.io-7B5CFF?logo=flydotio&logoColor=white)](https://fly.io/)

Note: Railway/Koyeb/Fly.io usually require a few console steps to “import from GitHub + build with Docker”. They don’t share a single standard “one-click clone” URL format like Render/Vercel/Netlify, so the buttons above link to the project creation entry points.

If you still want Cloudflare Pages / EdgeOne: host the static frontend separately on CF/EO, deploy the backend on Render/Railway, and point the frontend to that backend URL.

## Project structure

```text
.
├─ erpnext_coa_translator.py        # CLI converter: XML/CSV -> ERPNext COA CSV (+ optional translation)
├─ web/
│  ├─ server.py                    # FastAPI backend: FIFO jobs, SSE progress, download endpoint
│  └─ static/
│     └─ index.html                # Single-page UI (drag&drop, queue, progress, download)
├─ samples/                        # Committed sample outputs (safe to open)
├─ requirements.txt                # Python deps (CLI + Web)
├─ Dockerfile                      # Container build/run (uvicorn)
├─ docker-compose.yml              # Docker Compose (web server on :8000)
├─ render.yaml                     # Render deploy blueprint
├─ uctosnova.xml                   # Official XML input (optional to keep in repo)
├─ CIS_POLVYK.CSV                  # Official CSV input (optional to keep in repo)
├─ translation_cache.json          # Translation cache (used by CLI; can be regenerated)
└─ README*.md                      # Docs (EN/CZ/ZH)
```

## Security

- File names are NOT restricted. The server detects the format by content and validates structure (XML must contain `<row>` with expected fields; CSV must match CIS_POLVYK headers). Invalid files return a parsing error.
- API keys: the Web UI stores your key in your browser storage and sends it per job; the server does not persist API keys to disk and clears the in-memory key after the job starts.
- Upload limits & queue protection: configure via env vars: `MAX_UPLOAD_MB`, `MAX_QUEUE`, `MAX_JOBS`, `JOB_TTL_SECONDS`.
- If you ever committed a real API key, rotate/revoke it immediately.

## Quick start
```bash
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements.txt
python erpnext_coa_translator.py --input uctosnova.xml --offline
# or: python erpnext_coa_translator.py --input CIS_POLVYK.CSV --offline
# The CLI auto-detects XML vs CSV by content (filename/extension does not matter).
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
