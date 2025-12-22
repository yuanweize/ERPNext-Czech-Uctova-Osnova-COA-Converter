# ERPNext Czech Účtová Osnova (COA Converter) (Čeština)

- Účel: převod české směrné účtové osnovy (Směrná účtová osnova) do vícejazyčného CSV pro ERPNext (česky / anglicky / čínsky). Řeší kolize čísel účtů a limity délky názvů.
- Vstup: oficiální XML `uctosnova.xml` (ukázka přiložena).
- Výstup: `erpnext_coa_multilingual_YYYYMMDD_HHMM.csv` s časovým razítkem.
- Překlady: SiliconFlow / OpenRouter / OpenAI / Gemini, terminologie IPSAS/CAS; cache, retry a offline režim (bez API) podporovány.

## Rychlý start
1) Vytvořte a aktivujte virtuální prostředí.
2) `pip install -r requirements.txt`
3) Zkopírujte `.env.example` na `.env`, nastavte `PROVIDER` (siliconflow|openrouter|openai|gemini) a vyplňte příslušný API klíč (nebo použijte `--offline`). Výchozí stav nepřekládá (jen čeština); pro překlad nastavte `TRANSLATE_ENABLED=true` a jazykové kódy.
4) Spusťte:
```bash
python erpnext_coa_translator.py
```

## Konfigurace (.env)
- `PROVIDER`: `siliconflow|openrouter|openai|gemini`
- SiliconFlow: `SILICONFLOW_API_KEY`, `MODEL_ID` (výchozí `Qwen/Qwen2.5-72B-Instruct`)
- OpenRouter: `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` (výchozí `openai/gpt-4o`)
- OpenAI: `OPENAI_API_KEY`, `OPENAI_MODEL` (výchozí `gpt-4o-mini`)
- Gemini: `GEMINI_API_KEY`, `GEMINI_MODEL` (výchozí `gemini-1.5-flash`)
- Překlad: `TRANSLATE_ENABLED` (výchozí false pro čistě český výstup); `TRANSLATE_LANGS` (výchozí `en,zh`, pouze dva dvoupísmenné kódy). Příklady: `en,zh` -> cz/en/zh; `kr` -> cz/kr; `de,pl` -> cz/de/pl; více než dva kódy vyvolá chybu. Výstupní soubor nese jazykový tag, např. `erpnext_coa_CZ_EN_YYYYMMDD_HHMM.csv` (podtržítka kvůli kompatibilitě Windows).
- Runtime: `MAX_WORKERS`, `BATCH_SIZE`, `CURRENCY`, `LIMIT`, `OUTPUT_PREFIX`

## Datové zdroje
- CSV: https://monitor.statnipokladna.gov.cz/data/csv/CIS_POLVYK.CSV
- XML: https://monitor.statnipokladna.gov.cz/data/xml/uctosnova.xml
- XSD: https://monitor.statnipokladna.gov.cz/data/xsd/ciselniky/monitorUctosnova.xsd
- Datový katalog (aktualizované odkazy): https://data.gov.cz/dataset?iri=https%3A%2F%2Fdata.gov.cz%2Fzdroj%2Fdatov%C3%A9-sady%2F00006947%2F87ab86b58f0a0341acb8cb84ca4094fb

## Poznámky
- `translation_cache.json` ponechán jako ukázkový cache; `translation_cache_Qwen/` je ignorováno.
- Licence MIT, viz LICENSE.

## Struktura projektu (Tree)
- erpnext_coa_translator.py — hlavní skript pro překlad/generování
- translation_cache.json — ukázková cache
- CIS_POLVYK.CSV / uctosnova.xml — oficiální ukázková data
- README.md / README.cs.md / README.zh.md — dokumentace EN/CZ/ZH
- requirements.txt — závislosti
- .env.example — šablona konfigurace
- .gitignore — ignoruje venv, cache, časová razítka výstupů, dočasné složky
- erpnext_coa_multilingual_YYYYMMDD_HHMM.csv — generovaný výstup (ignorován)
- translation_cache_Qwen/ — dočasná cache (ignorováno)
