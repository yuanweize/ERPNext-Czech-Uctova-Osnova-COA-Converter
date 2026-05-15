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

### Root Type Mapping

| Class | Root Type | Logic |
|---|---|---|
| 0, 1, 2 | Asset | (2xx with P-marker → Liability) |
| 3 | Asset or Liability | Per A/P marker on each account |
| 4 (41-43, 49) | Equity | Share capital, retained earnings |
| 4 (45-48) | Liability | Provisions, long-term payables |
| 5 | Expense | All expense accounts |
| 6 | Income | All revenue accounts |
| 7 (701/702/710) | Equity | Closing accounts |

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

## 📄 License

MIT License. See [LICENSE](LICENSE).
