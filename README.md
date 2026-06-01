# ERPNext Czech Chart of Accounts Converter

[Česky](README.cs.md) | [中文](README.zh.md)

> **Enterprise-grade dual-mode** Czech Účtová osnova → ERPNext CSV converter.
> Supports **Commercial entities (s.r.o. / a.s.)** and **Public Sector (Státní pokladna)**.

---

## ✨ Features

| Feature | Commercial (Default) | Public Sector |
|---|---|---|
| **Data Source** | Built-in COA 2024 (Decree 500/2002) | Upload XML/CSV from data.gov.cz |
| **Root Types** | Asset / Liability / Equity / Expense / Income | Same |
| **Account Type** | Auto-mapped (Bank, Cash, Tax, Receivable, Payable…) | Manual |
| **File Upload** | Not required | Required |
| **Translation** | 🌍 AI-powered multilingual (EN/ZH/DE/…) | Same |

## 🚀 Quick Start

### Option A: CLI (Recommended)

```bash
# Clone & install
git clone https://github.com/YuanWeize/ERPNext-Czech-Uctova-Osnova-COA-Converter.git
cd ERPNext-Czech-Uctova-Osnova-COA-Converter
pip install -r requirements.txt
cp .env.example .env

# Generate Commercial COA (Czech only, offline)
python erpnext_coa_translator.py --offline

# Generate with AI translation (configure API key in .env first)
python erpnext_coa_translator.py

# Generate Public Sector COA
python erpnext_coa_translator.py --mode public_sector --input public_sector_data/uctosnova.xml --offline
```

### Option B: Web UI

```bash
uvicorn web.server:app --host 0.0.0.0 --port 8000
# Open http://localhost:8000
```

### Option C: Docker

```bash
docker compose up --build
```

## 📁 Project Structure

```
.
├── parsers/                       # COA parser modules
│   ├── base.py                    # Shared base class & utilities
│   ├── commercial_parser.py       # Commercial COA (Decree 500/2002)
│   └── public_sector_parser.py    # Public sector COA (Decree 410/2009)
├── data/commercial/               # Golden-source commercial data
│   └── uctova_osnova_2024.csv     # Curated from Stormware/Pohoda PDF
├── public_sector_data/            # Legacy public sector data
│   ├── uctosnova.xml
│   └── CIS_POLVYK.CSV
├── translation_engine.py          # LLM translation pipeline
├── erpnext_coa_translator.py      # CLI entry point
├── web/                           # FastAPI web interface
└── samples/                       # Example output CSVs
```

## 🏢 Commercial COA Architecture

The **Czech Standard Commercial Chart of Accounts** (Decree 500/2002 Coll.) uses a 3-level hierarchy:

| Level | Example | Description |
|---|---|---|
| **Class** (Třída) | `0` | Long-term Assets |
| **Group** (Skupina) | `02` | Tangible Fixed Assets |
| **Account** (Syntetický účet) | `022` | Tangible Movable Assets |

### Root Type Mapping (IFRS-Aligned)

ERPNext requires all nodes in a tree branch to share the same Root Type. The converter handles **mixed classes** (2, 3, 4) by splitting them — class-level nodes are omitted and groups are routed directly to the correct ERPNext root:

| Class | Root Type | Splitting Logic |
|---|---|---|
| 0, 1 | Asset | All accounts are Asset |
| 2 (21, 22, 25, 26, 29) | Asset | Cash, bank, short-term financial assets |
| 2 (23, 24) | **Liability** | Short-term loans, financial assistance |
| 3 (31, 35, 39) | Asset | Receivables, shareholder receivables |
| 3 (32, 33, 34, 36) | **Liability** | Payables, employee liabilities, tax |
| 3 (37, 38) | **Mixed** | Split per A/P marker; minority re-parented |
| 4 (41-43, 49) | **Equity** | Share capital, retained earnings |
| 4 (45-48) | **Liability** | Provisions, long-term payables |
| 5 | Expense | All expense accounts |
| 6 | Income | All revenue accounts |
| 7 (701/702/710) | Equity | Closing accounts |

> **Mixed group handling**: For groups containing both Asset (A) and Liability (P) accounts (e.g., group 33, 34, 37, 38), the majority `balance_side` determines the group's Root Type. Minority accounts are re-parented directly under the correct ERPNext root node.

### Auto-mapped ERPNext Account Types

- `211 Pokladna` → **Cash**
- `221 Peněžní prostředky na účtech` → **Bank**
- `311 Odběratelé` → **Receivable**
- `321 Dodavatelé` → **Payable**
- `343 DPH` → **Tax**
- `551 Odpisy…` → **Depreciation**
- `07x/08x Oprávky…` → **Accumulated Depreciation**
- `021-032 Stavby/Hmotné…` → **Fixed Asset**
- `5xx` → **Expense Account**
- `6xx` → **Income Account**

## 🌍 AI Translation

Supports **SiliconFlow**, **OpenRouter**, **OpenAI**, and **Gemini** as LLM providers. Configure in `.env`:

```env
TRANSLATE_ENABLED=true
TRANSLATE_LANGS=en,zh
PROVIDER=siliconflow
SILICONFLOW_API_KEY=your_key_here
```

## 📋 Changelog

### v2.0 (2026-06)

- **Root Type mapping rewrite** — IFRS-aligned, per-account routing based on `balance_side` (A/P) markers
- **Mixed-class splitting** — Classes 2/3/4 correctly split between Asset, Liability, and Equity
- **Name deduplication fix** — Account names no longer contain number prefixes that ERPNext would duplicate in "Standard with Numbers" mode
- **Account Number for groups** — Group nodes now carry their account number for proper sorting
- **Parent Account Number** — CSV now includes parent account numbers for better referencing

## 📄 License

MIT License. See [LICENSE](LICENSE).
