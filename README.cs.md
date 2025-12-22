# ERPNext Czech Účtová Osnova (COA Converter) (Čeština)

- Účel: převod české směrné účtové osnovy (Směrná účtová osnova) do vícejazyčného CSV pro ERPNext (česky / anglicky / čínsky). Řeší kolize čísel účtů a limity délky názvů.
- Vstup: oficiální XML `uctosnova.xml` (ukázka přiložena).
- Výstup: `erpnext_coa_multilingual_YYYYMMDD_HHMM.csv` s časovým razítkem.
- Překlady: SiliconFlow + Qwen, terminologie IPSAS/CAS; cache, retry a offline režim (bez API) podporovány.

## Rychlý start
1) Vytvořte a aktivujte virtuální prostředí.
2) `pip install -r requirements.txt`
3) Zkopírujte `.env.example` na `.env` a vyplňte `SILICONFLOW_API_KEY` (nebo použijte `--offline`).
4) Spusťte:
```bash
python erpnext_coa_translator.py
```

## Konfigurace (.env)
- `SILICONFLOW_API_KEY` (nutné pro překlad)
- `MODEL_ID` výchozí `Qwen/Qwen2.5-72B-Instruct`
- `MAX_WORKERS` / `BATCH_SIZE` pro souběh
- `CURRENCY` výchozí CZK
- `LIMIT` limit délky názvu v ERPNext (131)
- `OUTPUT_PREFIX` prefix názvu výstupu

## Datové zdroje
- CSV: https://monitor.statnipokladna.gov.cz/data/csv/CIS_POLVYK.CSV
- XML: https://monitor.statnipokladna.gov.cz/data/xml/uctosnova.xml
- XSD: https://monitor.statnipokladna.gov.cz/data/xsd/ciselniky/monitorUctosnova.xsd

## Poznámky
- `translation_cache.json` ponechán jako ukázkový cache; `translation_cache_Qwen/` je ignorováno.
- Licence MIT, viz LICENSE.
