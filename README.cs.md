# ERPNext Czech Účtová Osnova (COA Converter) (Čeština)

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

[English](README.md) | Čeština | [中文](README.zh.md)

Převod české směrné účtové osnovy (Směrná účtová osnova) do CSV, které lze importovat do ERPNext.

- Vstup: oficiální `uctosnova.xml` nebo `CIS_POLVYK.CSV` (název souboru nehraje roli; formát se ověřuje podle obsahu)
- Výstup: CSV se správnými kořeny (Asset/Liability/Equity/Income/Expense) a hierarchií
- Volitelný překlad: CZ + až 2 cílové jazyky (cache / retry / offline)

## Ukázkové soubory
Ukázkové CSV jsou součástí repozitáře (bez API klíčů):

- [samples/erpnext_coa_CZ_sample.csv](samples/erpnext_coa_CZ_sample.csv) — pouze CZ
- [samples/erpnext_coa_CZ_EN_sample.csv](samples/erpnext_coa_CZ_EN_sample.csv) — CZ/EN
- [samples/erpnext_coa_CZ_DE_RU_sample.csv](samples/erpnext_coa_CZ_DE_RU_sample.csv) — CZ/DE/RU
- [samples/erpnext_coa_CZ_ZH_RU_sample.csv](samples/erpnext_coa_CZ_ZH_RU_sample.csv) — CZ/ZH/RU


## Web UI (localhost / server)

Repo obsahuje jednoduché webové UI na jedné stránce: drag & drop upload (podporuje `uctosnova.xml` i `CIS_POLVYK.CSV`), FIFO frontu úloh, živý průběh (SSE) a stažení výsledného ERPNext CSV.

![Screenshot Web UI](https://github.com/user-attachments/assets/bd357431-8886-494e-919f-ab248fed833f)

- Lokálně:
	- `pip install -r requirements.txt`
	- `uvicorn web.server:app --reload`
	- Otevřete `http://127.0.0.1:8000`

- Jedním klikem nasadit (full stack včetně Python backendu):
	- [![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/yuanweize/ERPNext-Czech-Uctova-Osnova-COA-Converter)

Poznámka:
- Cloudflare Pages / EdgeOne / Vercel / Netlify jsou primárně pro statické weby, takže neumí přímo spustit tento Python backend (nelze jednou službou „upload → process → download“).
- Další Docker platformy (umí spustit tento repozitář přes Docker): Railway https://railway.app/new , Koyeb https://app.koyeb.com/ , Fly.io https://fly.io/

## Struktura projektu

```text
.
├─ erpnext_coa_translator.py        # CLI převodník: XML/CSV -> ERPNext COA CSV (+ volitelný překlad)
├─ web/
│  ├─ server.py                    # FastAPI backend: FIFO úlohy, SSE průběh, stažení výsledku
│  └─ static/
│     └─ index.html                # Jednostránkové UI (drag&drop, fronta, průběh, download)
├─ samples/                        # Ukázkové výstupy (commitované)
├─ requirements.txt                # Python závislosti (CLI + Web)
├─ Dockerfile                      # Docker běh (uvicorn)
├─ render.yaml                     # Render deploy blueprint
├─ uctosnova.xml                   # Oficiální XML vstup (volitelné)
├─ CIS_POLVYK.CSV                  # Oficiální CSV vstup (volitelné)
├─ translation_cache.json          # Cache překladů (pro CLI; lze znovu vygenerovat)
└─ README*.md                      # Dokumentace (EN/CZ/ZH)
```

## Bezpečnost

- Názvy souborů nejsou omezené. Server rozpozná formát podle obsahu a validuje strukturu (XML musí obsahovat `<row>` a očekávaná pole; CSV musí odpovídat hlavičkám CIS_POLVYK). Neplatné soubory vrátí chybu parsování.
- API klíče: UI je ukládá pouze v prohlížeči a posílá je pro konkrétní úlohu; server je neukládá na disk a po spuštění úlohy je z paměti odstraní.
- Ochrana proti zneužití: `MAX_UPLOAD_MB`, `MAX_QUEUE`, `MAX_JOBS`, `JOB_TTL_SECONDS`.

## Rychlý start
```bash
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements.txt
python erpnext_coa_translator.py --input uctosnova.xml --offline
# nebo: python erpnext_coa_translator.py --input CIS_POLVYK.CSV --offline
# CLI rozpozná XML vs CSV podle obsahu (název/koncovka souboru není důležitá).
```

Pro překlady: zkopírujte `.env.example` -> `.env`, nastavte `PROVIDER=...` a příslušný API klíč, pak `TRANSLATE_ENABLED=true`.

## Pojmenování výstupů
Generované výstupy jsou gitignore a mají časové razítko (na minutu):

- Výchozí prefix: `OUTPUT_PREFIX=erpnext_coa_multilingual`
- Jen CZ: `erpnext_coa_multilingual_CZ_YYYYMMDD_HHMM.csv`
- S jazyky: `erpnext_coa_multilingual_CZ_EN_ZH_YYYYMMDD_HHMM.csv`

Jazykové tagy jsou oddělené podtržítky kvůli Windows kompatibilitě.

## Konfigurace (.env)
| Proměnná | Význam |
|---|---|
| `PROVIDER` | `siliconflow\|openrouter\|openai\|gemini` |
| `SILICONFLOW_API_KEY` / `MODEL_ID` | SiliconFlow klíč / model |
| `OPENROUTER_API_KEY` / `OPENROUTER_MODEL` | OpenRouter klíč / model |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | OpenAI klíč / model |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | Gemini klíč / model (OpenAI kompatibilní endpoint) |
| `TRANSLATE_ENABLED` | `true` zapne překlady (default `false`) |
| `TRANSLATE_LANGS` | dvoupísmenné kódy, max 2 (default `en,zh`) |
| `MAX_WORKERS` / `BATCH_SIZE` | paralelismus / dávkování |
| `CURRENCY` | měna účtů (default `CZK`) |
| `LIMIT` | limit délky názvu (default `131`) |
| `OUTPUT_PREFIX` | prefix výstupního souboru |

## Datové zdroje (oficiální)
- CSV: https://monitor.statnipokladna.gov.cz/data/csv/CIS_POLVYK.CSV
- XML: https://monitor.statnipokladna.gov.cz/data/xml/uctosnova.xml
- XSD: https://monitor.statnipokladna.gov.cz/data/xsd/ciselniky/monitorUctosnova.xsd
- Datový katalog: https://data.gov.cz/dataset?iri=https%3A%2F%2Fdata.gov.cz%2Fzdroj%2Fdatov%C3%A9-sady%2F00006947%2F87ab86b58f0a0341acb8cb84ca4094fb

## Technologický stack a návrh
- Python 3.10+, minimum závislostí (`requests`, `python-dotenv`, volitelně `tqdm`).
- Jeden integrační styl: OpenAI-kompatibilní chat API.
- Cache + backoff + retry pro stabilní výstupy.
- ERPNext specifika: hierarchie, duplicity čísel účtů, délkové limity.

## Licence
MIT, viz LICENSE.
