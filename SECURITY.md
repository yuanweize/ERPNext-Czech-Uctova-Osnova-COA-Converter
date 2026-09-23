# Security Policy

## Supported Versions

| Version | Supported          | Notes |
| ------- | ------------------ | ----- |
| 1.0.x   | :white_check_mark: | Current active release line |

## Financial Data & Secret Safety

ERPNext-Czech-Uctova-Osnova-COA-Converter handles accounting taxonomy and LLM translation APIs:

1. **No Sensitive Account Numbers or Ledgers**: Standard Czech chart of accounts (Decree 500/2002 Sb.) is public regulatory schema. However, never commit private organizational ledgers or confidential financial records.
2. **API Key Protection**: AI translation uses external LLM APIs (Anthropic Claude or OpenAI). Keys must be passed via environment variables (`.env`) and never committed into git or exposed in client responses.
3. **File Upload Hardening**: Uploaded chart of accounts files are parsed in isolated memory streams with strict size and format validation (CSV/PDF).

## Reporting a Vulnerability

If you discover a security vulnerability or credential leak:

1. **Do NOT open a public issue.**
2. Report privately via [GitHub Security Advisories](https://github.com/yuanweize/ERPNext-Czech-Uctova-Osnova-COA-Converter/security/advisories/new) or contact `yuanweize@users.noreply.github.com`.
3. Provide details and reproduction steps.
4. I aim to acknowledge valid security reports as soon as practical, investigate the root cause, and coordinate a patch.
