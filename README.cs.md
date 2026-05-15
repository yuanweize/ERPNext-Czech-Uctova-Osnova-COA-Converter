# ERPNext – Převodník české účtové osnovy

[English](README.md) | [中文](README.zh.md)

> **Profesionální dvourežimový** převodník české účtové osnovy do formátu ERPNext CSV.
> Podporuje **podnikatelské subjekty (s.r.o. / a.s.)** a **veřejný sektor (Státní pokladna)**.

---

## ✨ Funkce

| Funkce | Komerční režim (výchozí) | Veřejný sektor |
|---|---|---|
| **Datový zdroj** | Vestavěná účtová osnova 2024 (vyhláška 500/2002) | Nahrání XML/CSV z data.gov.cz |
| **Root Types** | Asset / Liability / Equity / Expense / Income | Stejné |
| **Account Type** | Automatické mapování (Bank, Cash, Tax…) | Manuální |
| **Nahrání souboru** | Není potřeba | Povinné |
| **Překlad** | 🌍 AI překlad (EN/ZH/DE/…) | Stejné |

## 🚀 Rychlý start

```bash
# Klonování a instalace
git clone https://github.com/YuanWeize/ERPNext-Czech-Uctova-Osnova-COA-Converter.git
cd ERPNext-Czech-Uctova-Osnova-COA-Converter
pip install -r requirements.txt
cp .env.example .env

# Generování komerční účtové osnovy (pouze česky, offline)
python erpnext_coa_translator.py --offline

# S AI překladem (nejdříve nastavte API klíč v .env)
python erpnext_coa_translator.py

# Generování účtové osnovy veřejného sektoru
python erpnext_coa_translator.py --mode public_sector --input public_sector_data/uctosnova.xml --offline
```

## 🏢 Architektura komerční účtové osnovy

Založená na **vyhlášce 500/2002 Sb.** se standardní tříúrovňovou hierarchií:

| Úroveň | Příklad | Popis |
|---|---|---|
| **Třída** | `0` | Dlouhodobý majetek |
| **Skupina** | `02` | Dlouhodobý hmotný majetek |
| **Syntetický účet** | `022` | Hmotné movité věci |

### Mapování Root Type

| Třída | ERPNext Root Type | Logika |
|---|---|---|
| 0, 1, 2 | Asset | (2xx s P-značkou → Liability) |
| 3 | Asset nebo Liability | Podle A/P značky účtu |
| 4 (41-43, 49) | Equity | Základní kapitál, fondy |
| 4 (45-48) | Liability | Rezervy, dlouhodobé závazky |
| 5 | Expense | Nákladové účty |
| 6 | Income | Výnosové účty |
| 7 (701/702/710) | Equity | Závěrkové účty |

### Automaticky mapované Account Types

- `211 Pokladna` → **Cash**
- `221 Peněžní prostředky na účtech` → **Bank**
- `311 Odběratelé` → **Receivable**
- `321 Dodavatelé` → **Payable**
- `343 DPH` → **Tax**
- `551 Odpisy` → **Depreciation**
- `07x/08x Oprávky` → **Accumulated Depreciation**

## 🌍 AI Překlad

Podporuje **SiliconFlow**, **OpenRouter**, **OpenAI** a **Gemini**. Nastavení v `.env`:

```env
TRANSLATE_ENABLED=true
TRANSLATE_LANGS=en,zh
PROVIDER=siliconflow
SILICONFLOW_API_KEY=your_key_here
```

## 📄 Licence

MIT License. Viz [LICENSE](LICENSE).
