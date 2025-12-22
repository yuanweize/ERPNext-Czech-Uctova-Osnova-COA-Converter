# ERPNext Czech Účtová Osnova (COA Converter) (Čeština)

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

Převod české směrné účtové osnovy (Směrná účtová osnova) do CSV, které lze importovat do ERPNext.

- Vstup: oficiální `uctosnova.xml`
- Výstup: CSV se správnými kořeny (Asset/Liability/Equity/Income/Expense) a hierarchií
- Volitelný překlad: CZ + až 2 cílové jazyky (cache / retry / offline)

## Ukázkové soubory
Ukázkové CSV jsou součástí repozitáře (bez API klíčů):

- [erpnext_coa_CZ_sample.csv](erpnext_coa_CZ_sample.csv) — pouze CZ
- [erpnext_coa_CZ_EN_sample.csv](erpnext_coa_CZ_EN_sample.csv) — CZ/EN
- [erpnext_coa_CZ_DE_RU_sample.csv](erpnext_coa_CZ_DE_RU_sample.csv) — CZ/DE/RU
- [erpnext_coa_CZ_ZH_RU_sample.csv](erpnext_coa_CZ_ZH_RU_sample.csv) — CZ/ZH/RU

## Rychlý start
```bash
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements.txt
python erpnext_coa_translator.py --offline
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
