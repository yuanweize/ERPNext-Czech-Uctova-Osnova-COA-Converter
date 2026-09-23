# Contributing to ERPNext Czech COA Converter

Thank you for contributing! This project bridges Czech statutory accounting (Vyhláška 500/2002 Sb.) with modern ERPNext chart of accounts structures.

## Development Setup

### Prerequisites

- Python 3.10+
- (Optional) Anthropic Claude or OpenAI API key for translation evaluation

### Local Setup

```bash
git clone https://github.com/yuanweize/ERPNext-Czech-Uctova-Osnova-COA-Converter.git
cd ERPNext-Czech-Uctova-Osnova-COA-Converter

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Running the Web Interface

```bash
uvicorn web.app:app --reload --port 8000
```

## Contribution Workflow

1. Create a feature branch (`git checkout -b feat/your-feature-name`).
2. Adhere to Python PEP 8 formatting guidelines.
3. Validate parser changes against sample datasets in `samples/`.
4. Submit a Pull Request describing your changes and verification steps.
