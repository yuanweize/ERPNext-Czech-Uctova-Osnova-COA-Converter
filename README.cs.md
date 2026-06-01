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

### Mapování Root Type (v souladu s IFRS)

ERPNext vyžaduje, aby všechny uzly ve větvi stromu sdílely stejný Root Type. Převodník řeší **smíšené třídy** (2, 3, 4) jejich rozdělením — uzly úrovně třídy jsou vynechány a skupiny jsou směrovány přímo na správný kořen ERPNext:

| Třída | ERPNext Root Type | Logika rozdělení |
|---|---|---|
| 0, 1 | Asset | Všechny účty jsou aktiva |
| 2 (21, 22, 25, 26, 29) | Asset | Hotovost, banka, krátkodobý fin. majetek |
| 2 (23, 24) | **Liability** | Krátkodobé úvěry, finanční výpomoci |
| 3 (31, 35, 39) | Asset | Pohledávky |
| 3 (32, 33, 34, 36) | **Liability** | Závazky, zaměstnanci, daně |
| 3 (37, 38) | **Smíšené** | Rozděleno podle A/P; menšina přeřazena |
| 4 (41-43, 49) | **Equity** | Základní kapitál, fondy |
| 4 (45-48) | **Liability** | Rezervy, dlouhodobé závazky |
| 5 | Expense | Nákladové účty |
| 6 | Income | Výnosové účty |
| 7 (701/702/710) | Equity | Závěrkové účty |

> **Smíšené skupiny**: U skupin s účty A i P (např. 33, 34, 37, 38) většinová `balance_side` určuje Root Type skupiny. Menšinové účty jsou přeřazeny přímo pod správný kořen ERPNext.

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

## 📋 Změny

### v2.0 (2026-06)

- **Přepis mapování Root Type** — v souladu s IFRS, směrování podle `balance_side` (A/P)
- **Rozdělení smíšených tříd** — Třídy 2/3/4 správně rozděleny mezi Asset, Liability a Equity
- **Oprava duplicitních čísel** — Názvy účtů již neobsahují číselné předpony
- **Čísla účtů pro skupiny** — Skupinové uzly nyní nesou číslo účtu
- **Číslo nadřazeného účtu** — CSV nyní obsahuje čísla nadřazených účtů

## 📄 Licence

MIT License. Viz [LICENSE](LICENSE).
