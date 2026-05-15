"""Translation engine – provider-agnostic LLM translation with caching.

Extracted from the legacy erpnext_coa_translator.py to be shared by both
commercial and public-sector pipelines.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import product
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

load_dotenv()

# ================= Configuration (override via .env) =================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Provider selection: siliconflow | openrouter | openai | gemini
PROVIDER = os.getenv("PROVIDER", "siliconflow").lower()

# SiliconFlow
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY", "")
MODEL_ID = os.getenv("MODEL_ID", "Qwen/Qwen2.5-72B-Instruct")

# OpenRouter
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o")

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# Concurrency
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "16"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "8"))

# ERPNext name length limit
LIMIT = int(os.getenv("LIMIT", "131"))

# Translation toggles
DEFAULT_LANGS = ["en", "zh"]
TRANSLATE_ENABLED = os.getenv("TRANSLATE_ENABLED", "false").strip().lower() == "true"
RAW_TRANSLATE_LANGS = os.getenv("TRANSLATE_LANGS", "en,zh")


def parse_lang_codes(raw: str) -> List[str]:
    langs: List[str] = []
    for part in raw.split(","):
        code = part.strip().lower()
        if code and code not in langs:
            langs.append(code)
    return langs


def validate_translation_settings(enabled: bool, langs: List[str]) -> List[str]:
    if not enabled:
        return []
    if not langs:
        langs = list(DEFAULT_LANGS)
    if len(langs) > 2:
        print(f"❌ TRANSLATE_LANGS supports at most 2 codes; got: {langs}")
        sys.exit(1)
    for code in langs:
        if len(code) != 2 or not code.isalpha():
            print(f"❌ Invalid language code '{code}'. Use two-letter codes.")
            sys.exit(1)
    return langs


TRANSLATE_LANGS = validate_translation_settings(
    TRANSLATE_ENABLED, parse_lang_codes(RAW_TRANSLATE_LANGS)
)
TARGET_LANGS = TRANSLATE_LANGS if TRANSLATE_ENABLED else []

PROVIDERS: Dict[str, Dict[str, Any]] = {
    "siliconflow": {
        "api_key": SILICONFLOW_API_KEY,
        "model": MODEL_ID,
        "base_url": "https://api.siliconflow.cn/v1",
        "extra_headers": None,
    },
    "openrouter": {
        "api_key": OPENROUTER_API_KEY,
        "model": OPENROUTER_MODEL,
        "base_url": "https://openrouter.ai/api/v1",
        "extra_headers": {"X-Title": "ERPNext Czech COA Converter"},
    },
    "openai": {
        "api_key": OPENAI_API_KEY,
        "model": OPENAI_MODEL,
        "base_url": "https://api.openai.com/v1",
        "extra_headers": None,
    },
    "gemini": {
        "api_key": GEMINI_API_KEY,
        "model": GEMINI_MODEL,
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "extra_headers": None,
    },
}

# Cache file
CACHE_FILE = os.path.join(CURRENT_DIR, "translation_cache.json")
SECONDARY_CACHE_FILE = os.path.join(
    CURRENT_DIR, "translation_cache_Qwen", "translation_cache.json"
)


# ---------------------------------------------------------------------------
# Normalization (re-exported for convenience)
# ---------------------------------------------------------------------------

def normalize_term(term: str) -> str:
    """Normalize Czech names to avoid cache misses."""
    if not isinstance(term, str):
        return ""
    import re
    term = term.replace("\xa0", " ")
    term = re.sub(r"^['\"]+", "", term.strip())
    term = re.sub(r"['\":]+$", "", term)
    term = re.sub(r"\s+", " ", term)
    return term


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                raw_cache = json.load(f)
            normalized: dict = {}
            changed = False
            for k, v in raw_cache.items():
                nk = normalize_term(k)
                if nk != k:
                    changed = True
                normalized.setdefault(nk, v)

            if os.path.exists(SECONDARY_CACHE_FILE):
                with contextlib.suppress(Exception):
                    with open(SECONDARY_CACHE_FILE, "r", encoding="utf-8") as f2:
                        for k, v in json.load(f2).items():
                            normalized.setdefault(normalize_term(k), v)

            if changed:
                save_cache(normalized)
            return normalized
        except Exception:
            return {}
    return {}


def save_cache(cache: dict) -> None:
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Prompt & API call
# ---------------------------------------------------------------------------

def _needs_translation(entry: Optional[dict], target_langs: List[str]) -> bool:
    if not target_langs:
        return False
    if not entry:
        return True
    return any(not entry.get(f"{lang}_full") for lang in target_langs)


def build_prompt(batch_terms: List[str], target_langs: List[str], mode: str = "commercial") -> str:
    langs = target_langs or DEFAULT_LANGS
    lang_list_str = ", ".join(langs)
    field_lines = []
    for lang in langs:
        upper = lang.upper()
        field_lines.append(f'            "{lang}_full": "Formal {upper} name"')
        field_lines.append(f'            "{lang}_short": "Concise {upper} abbreviation"')
    fields_block = ",\n".join(field_lines)

    if mode == "commercial":
        role_desc = (
            "You are a Lead Partner at a Big 4 firm specializing in Czech commercial "
            "accounting (Decree 500/2002 Coll., Czech Accounting Standards for Entrepreneurs)."
        )
        rules = """
    ### ⚠️ Strict Czech-to-target mapping rules (Commercial):
    1. **"Závazky"** → EN: "Liabilities" / ZH: "负债"
    2. **"Rezervy"** → EN: "Provisions" (NOT Reserves) / ZH: "准备金"
    3. **"Pohledávky"** → EN: "Receivables" / ZH: "应收账款"
    4. **"Dodavatelé"** → EN: "Trade Payables" or "Suppliers" / ZH: "应付账款-供应商"
    5. **"Odběratelé"** → EN: "Trade Receivables" or "Customers" / ZH: "应收账款-客户"
    6. **"Oprávky"** → EN: "Accumulated Depreciation" / ZH: "累计折旧"
    7. **"Opravné položky"** → EN: "Allowances" or "Provisions for impairment" / ZH: "减值准备"
    8. **"Základní kapitál"** → EN: "Share Capital" / ZH: "注册资本"
    9. **"Pokladna"** → EN: "Cash on Hand" / ZH: "库存现金"
    10. **"Peněžní prostředky na účtech"** → EN: "Bank Accounts" / ZH: "银行存款"

    ### 💎 Quality Benchmarks:
    - **Terminology**: EN must align with **IFRS**; ZH must align with **CAS** (Chinese Accounting Standards).
    - **Logic**: Translate the financial *meaning*, not the literal Czech words.
    - **Abbreviations**: Provide short versions suitable for ERPNext name length limits.
    """
    else:
        role_desc = (
            "You are a Lead Partner at a Big 4 firm and a former consultant for "
            "the Czech Ministry of Finance, expert in Decree No. 410/2009 Coll. "
            "(Czech Public Sector Accounting)."
        )
        rules = """
    ### ⚠️ Strict Czech-to-target mapping rules (Public Sector):
    1. **"Cizí zdroje"** → EN: "Liabilities" (NEVER "Resources") / ZH: "负债"
    2. **"Rezervy"** → EN: "Provisions" (Never "Reserves") / ZH: "准备金"
    3. **"Státní příspěvkové organizace"** → EN: "State Budgetary Organizations" / ZH: "国家预算单位"
    4. **"Územní samosprávný celek"** → EN: "Local Government Units" / ZH: "地方政府单位"
    5. **"Běžný účet"** → EN: "Current Bank Account" / ZH: "银行存款"
    6. **"Jmění"** → EN: "Equity / Net Assets" / ZH: "净资产"
    7. **"Ceniny"** → EN: "Cash Equivalents (Vouchers/Stamps)" / ZH: "有价票证"

    ### 💎 Quality Benchmarks:
    - **Terminology**: EN must align with **IPSAS**; ZH must align with **CAS/GOP**.
    - **Logic**: Translate financial meaning, not literal words.
    """

    return f"""
    Role: {role_desc}

    Task: Translate Czech COA items into the requested languages with impeccable accuracy.

    Target languages (two-letter codes, max 2): {lang_list_str}

    {rules}

    ### 📥 Input Data:
    {json.dumps(batch_terms, ensure_ascii=False)}

    ### 📤 Output Format (Strict JSON):
    {{
        "Czech Original": {{
{fields_block}
        }}
    }}

    Only return the JSON object. Do not add explanations.
    """


def _post_with_backoff(url, headers, payload, extract_fn):
    backoff = 2
    for _ in range(6):
        try:
            resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
            if resp.status_code == 200:
                return extract_fn(resp)
            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)
                continue
        except Exception:
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)
    return None


def _call_openai_compatible(batch_terms, target_langs, api_key, model, base_url,
                            extra_headers=None, mode="commercial"):
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if extra_headers:
        headers.update({k: v for k, v in extra_headers.items() if v})
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": build_prompt(batch_terms, target_langs, mode)}],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    return _post_with_backoff(
        url, headers, payload,
        lambda r: json.loads(r.json()["choices"][0]["message"]["content"]),
    )


def call_provider(batch_terms: List[str], target_langs: List[str],
                  mode: str = "commercial") -> Optional[dict]:
    config = PROVIDERS.get(PROVIDER)
    if not config:
        print(f"Unknown provider: {PROVIDER}")
        return None
    return _call_openai_compatible(
        batch_terms, target_langs,
        api_key=config["api_key"],
        model=config["model"],
        base_url=config["base_url"],
        extra_headers=config.get("extra_headers"),
        mode=mode,
    )


def provider_key_missing() -> bool:
    config = PROVIDERS.get(PROVIDER, {})
    return not config.get("api_key")


# ---------------------------------------------------------------------------
# Batch translation runner
# ---------------------------------------------------------------------------

def _pick_worker_count(total_terms: int) -> int:
    return max(4, min(MAX_WORKERS, max(4, total_terms // 5)))


def run_batches(terms, cache, batch_size, workers, target_langs,
                stage_label="main", mode="commercial"):
    batches = [terms[i: i + batch_size] for i in range(0, len(terms), batch_size)]
    total = len(terms)
    done_terms = 0
    done_batches = 0
    missing: List[str] = []

    pbar = None
    if os.environ.get("DISABLE_TQDM") != "1":
        try:
            from tqdm import tqdm
            pbar = tqdm(total=total, desc=f"{stage_label} translation", unit="term", dynamic_ncols=True)
        except Exception:
            pass

    print(f"   -> {stage_label}: threads {workers}, batch size {batch_size}")
    with ThreadPoolExecutor(max_workers=workers) as executor:
        fmap = {executor.submit(call_provider, b, target_langs, mode): b for b in batches}
        for future in as_completed(fmap):
            batch = fmap[future]
            result = future.result()
            if result:
                for k, v in result.items():
                    nk = normalize_term(k)
                    existing = cache.get(nk, {}) if isinstance(cache.get(nk, {}), dict) else {}
                    cache[nk] = {**existing, **v}
            for t in batch:
                if normalize_term(t) not in cache:
                    missing.append(t)
            done_batches += 1
            done_terms += len(batch)
            if pbar:
                pbar.update(len(batch))
                pbar.set_postfix_str(f"batch {done_batches}/{len(batches)}")
            else:
                print(f"   -> {stage_label}: {done_terms}/{total} terms", flush=True)

    if pbar:
        with contextlib.suppress(Exception):
            pbar.close()
    return missing


def translate_terms(
    unique_names: List[str],
    *,
    offline: bool = False,
    mode: str = "commercial",
) -> dict:
    """Run the full translation pipeline and return the populated cache."""
    cache = load_cache()
    target_langs = TARGET_LANGS

    if not target_langs:
        print("\n>>> 翻译开关已关闭：仅输出捷克语（cz）到 CSV。")
        return cache

    new_terms = [t for t in unique_names if _needs_translation(cache.get(t), target_langs)]

    if new_terms and not offline:
        total = len(new_terms)
        print(f"\n>>> 🚀 启动翻译({','.join(target_langs)}): {total} 个词条")
        bs = BATCH_SIZE
        workers = _pick_worker_count(total)

        missing = run_batches(new_terms, cache, bs, workers, target_langs, "首轮", mode)
        retry = 1
        while missing and retry <= 2:
            print(f"   -> 补偿第{retry}轮: {len(missing)} 词条")
            missing = run_batches(missing, cache, min(bs, 4), min(workers, 4),
                                  target_langs, f"补偿{retry}", mode)
            retry += 1
        if missing:
            print(f"   -> 仍缺失 {len(missing)} 词条")
        else:
            print("   -> 翻译已全部落库")
        save_cache(cache)
    elif new_terms and offline:
        print(f"\n>>> offline 模式：跳过 {len(new_terms)} 个新词条的翻译")

    return cache


# ---------------------------------------------------------------------------
# Name building
# ---------------------------------------------------------------------------

def build_name(code: str, cz: str, trans_data: Optional[dict],
               target_langs: List[str]) -> str:
    """Build a multilingual account name that fits within LIMIT chars."""
    if not target_langs or not trans_data:
        return f"{code} - {cz}"[:LIMIT]

    lang_entries = []
    for lang in target_langs:
        full = trans_data.get(f"{lang}_full", "")
        short = trans_data.get(f"{lang}_short", full)
        if full:
            lang_entries.append((lang, full, short))

    if not lang_entries:
        return f"{code} - {cz}"[:LIMIT]

    for keep in range(len(lang_entries), 0, -1):
        subset = lang_entries[:keep]
        choice_lists = []
        for _, full, short in subset:
            opts = [full]
            if short and short != full:
                opts.append(short)
            choice_lists.append(opts)
        for combo in product(*choice_lists):
            parts = [cz] + list(combo)
            candidate = f"{code} - " + " / ".join(parts)
            if len(candidate) <= LIMIT:
                return candidate

    return f"{code} - {cz}"[:LIMIT]
