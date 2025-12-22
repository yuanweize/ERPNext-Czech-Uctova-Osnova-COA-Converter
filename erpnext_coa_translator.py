import xml.etree.ElementTree as ET
import csv
import os
import json
import time
import re
import sys
import argparse
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import product
import requests
import contextlib
from dotenv import load_dotenv

load_dotenv()

# ================= Configuration (override via .env) =================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Provider selection: siliconflow | openrouter | openai | gemini
PROVIDER = os.getenv("PROVIDER", "siliconflow").lower()

# SiliconFlow
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY", "")
MODEL_ID = os.getenv("MODEL_ID", "Qwen/Qwen2.5-72B-Instruct")

# OpenRouter (OpenAI-compatible endpoint)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o")

# OpenAI (native endpoint)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Gemini (OpenAI-compatible endpoint)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# Concurrency
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "16"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "8"))

# Currency
CURRENCY = os.getenv("CURRENCY", "CZK")

# ERPNext name length limit
LIMIT = int(os.getenv("LIMIT", "131"))

# Output prefix (timestamp to minutes will be appended)
OUTPUT_PREFIX = os.getenv("OUTPUT_PREFIX", "erpnext_coa_multilingual")

# Translation toggles
TRANSLATE_ENABLED = os.getenv("TRANSLATE_ENABLED", "false").strip().lower() == "true"
DEFAULT_LANGS = ["en", "zh"]
RAW_TRANSLATE_LANGS = os.getenv("TRANSLATE_LANGS", "en,zh")


def parse_lang_codes(raw: str):
    langs = []
    for part in raw.split(','):
        code = part.strip().lower()
        if code and code not in langs:
            langs.append(code)
    return langs


def validate_translation_settings(enabled: bool, langs):
    if not enabled:
        return []
    if not langs:
        langs = list(DEFAULT_LANGS)
    if len(langs) > 2:
        print(f"❌ TRANSLATE_LANGS supports at most 2 codes; got: {langs}")
        sys.exit(1)
    for code in langs:
        if len(code) != 2 or not code.isalpha():
            print(f"❌ Invalid language code '{code}'. Use two-letter codes, e.g., en, zh, de, pl, kr")
            sys.exit(1)
    return langs


TRANSLATE_LANGS = validate_translation_settings(TRANSLATE_ENABLED, parse_lang_codes(RAW_TRANSLATE_LANGS))
TARGET_LANGS = TRANSLATE_LANGS if TRANSLATE_ENABLED else []

PROVIDERS = {
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

# Data files
DEFAULT_INPUT_FILE = os.path.join(CURRENT_DIR, 'uctosnova.xml')
CACHE_FILE = os.path.join(CURRENT_DIR, 'translation_cache.json')
SECONDARY_CACHE_FILE = os.path.join(CURRENT_DIR, 'translation_cache_Qwen', 'translation_cache.json')

# --- 根节点名称 ---
ROOT_ASSET = "Assets - Aktiva - 资产"
ROOT_LIAB = "Liabilities - Pasiva - 负债"
ROOT_EQUITY = "Equity - Vlastní kapitál - 权益"
ROOT_EXP = "Expenses - Náklady - 费用"
ROOT_INC = "Income - Výnosy - 收入"


def normalize_term(term: str) -> str:
    """Normalize Czech names to avoid cache misses caused by NBSP or stray punctuation."""
    if not isinstance(term, str):
        return ""
    term = term.replace('\xa0', ' ')
    term = re.sub(r"^['\"]+", "", term.strip())
    term = re.sub(r"['\":]+$", "", term)
    term = re.sub(r"\s+", " ", term)
    return term


def get_node_text(node, tag_name):
    element = node.find(tag_name)
    if element is not None and element.text is not None:
        return element.text.strip()
    return ""


def _date_yyyymmdd_to_ddmmyyyy(s: str) -> str:
    s = (s or "").strip().strip('"')
    if not s:
        return ""
    if re.fullmatch(r"\d{8}", s):
        return f"{s[6:8]}-{s[4:6]}-{s[0:4]}"
    return s


def _normalize_vykaz(v: str) -> str:
    v = (v or "").strip().strip('"')
    v = v.lstrip('0')
    return v or "0"


def load_rows_from_xml(input_file: str):
    try:
        tree = ET.parse(input_file)
        root = tree.getroot()
    except Exception as e:
        raise RuntimeError(f"XML 解析失败: {e}")

    rows = []
    for row in root.findall('row'):
        rows.append({
            "vykaz": get_node_text(row, 'vykaz'),
            "polvyk": get_node_text(row, 'polvyk'),
            "polvyk_nazev": get_node_text(row, 'polvyk_nazev'),
            "synuc": get_node_text(row, 'synuc'),
            "end_date": get_node_text(row, 'end_date'),
            "start_date": get_node_text(row, 'start_date'),
        })
    return rows


def load_rows_from_cis_polvyk_csv(input_file: str):
    # CIS_POLVYK.CSV is semicolon-delimited, fields are quoted.
    # We map it to the same shape as XML rows.
    rows = []
    with open(input_file, 'r', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f, delimiter=';')
        for r in reader:
            vykaz = _normalize_vykaz(r.get('/BIC/ZC_VYKAZ Výkaz', ''))
            polvyk = (r.get('/BIC/ZC_POLVYK Položka výkazu', '') or '').strip().strip('"')
            synuc = (r.get('/BIC/ZC_SYNUC Syntetický účet', '') or '').strip().strip('"')
            name = (r.get('TXTXL Dlouhý text', '') or '').strip().strip('"')
            datefrom = _date_yyyymmdd_to_ddmmyyyy(r.get('DATEFROM Platí od', ''))
            dateto_raw = (r.get('DATETO Platí do', '') or '').strip().strip('"')
            dateto = _date_yyyymmdd_to_ddmmyyyy(dateto_raw)

            rows.append({
                "vykaz": vykaz,
                "polvyk": polvyk,
                "polvyk_nazev": name,
                "synuc": synuc,
                "start_date": datefrom,
                "end_date": dateto or dateto_raw,
            })
    return rows


def load_rows_auto(input_file: str):
    ext = os.path.splitext(input_file)[1].lower()

    def _sniff() -> str:
        try:
            with open(input_file, 'rb') as f:
                head = f.read(4096).lstrip()
        except Exception:
            return ""
        if head.startswith(b"<"):
            return "xml"
        return "csv"

    # Prefer extension when provided, but fall back to content sniffing.
    if ext == ".xml":
        try:
            return load_rows_from_xml(input_file)
        except Exception:
            # extension might be wrong
            return load_rows_from_cis_polvyk_csv(input_file)
    if ext == ".csv":
        try:
            return load_rows_from_cis_polvyk_csv(input_file)
        except Exception:
            return load_rows_from_xml(input_file)

    kind = _sniff()
    if kind == "xml":
        return load_rows_from_xml(input_file)
    if kind == "csv":
        return load_rows_from_cis_polvyk_csv(input_file)
    raise RuntimeError(f"Unsupported input type or unreadable file: {input_file}")


def is_current_row(end_date: str) -> bool:
    # XML uses 31-12-9999; CSV uses 99991231
    s = str(end_date or "")
    return ("9999" in s) or ("99991231" in s)


def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                raw_cache = json.load(f)
            normalized_cache = {}
            changed = False
            for k, v in raw_cache.items():
                nk = normalize_term(k)
                if nk != k:
                    changed = True
                normalized_cache.setdefault(nk, v)

            if os.path.exists(SECONDARY_CACHE_FILE):
                try:
                    with open(SECONDARY_CACHE_FILE, 'r', encoding='utf-8') as f2:
                        secondary_raw = json.load(f2)
                    for k, v in secondary_raw.items():
                        nk = normalize_term(k)
                        normalized_cache.setdefault(nk, v)
                except:
                    pass

            if changed:
                save_cache(normalized_cache)
            return normalized_cache
        except:
            return {}
    return {}


def save_cache(cache):
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def needs_translation_for_langs(cache_entry: dict, target_langs) -> bool:
    if not target_langs:
        return False
    if not cache_entry:
        return True
    for lang in target_langs:
        if not cache_entry.get(f"{lang}_full"):
            return True
    return False


def build_prompt(batch_terms, target_langs):
    langs = target_langs or DEFAULT_LANGS
    lang_list_str = ", ".join(langs)
    field_lines = []
    for lang in langs:
        upper = lang.upper()
        field_lines.append(f'            "{lang}_full": "Formal {upper} name"')
        field_lines.append(f'            "{lang}_short": "Concise {upper} abbreviation"')
    fields_block = ",\n".join(field_lines)

    return f"""

    Role: You are a Lead Partner at a Big 4 firm and a former consultant for the Czech Ministry of Finance.

    You are the world's leading expert in Decree No. 410/2009 Coll. (Czech Public Sector Accounting).

    Task: Translate Czech COA items into the requested languages with impeccable accuracy.

    Target languages (two-letter codes, max 2): {lang_list_str}

    ### ⚠️ Strict Czech-to-target mapping rules:
    1. **"Cizí zdroje" (Fundamental Identity)**:
       - English: MUST be "Liabilities" (NEVER "Resources").
       - Chinese: MUST be "负债" (NEVER "外来资源").

    2. **"Rezervy" (Provisions)**:
       - English: "Provisions" (Never "Reserves").
       - Chinese: "预计负债" or "准备金".

    3. **"Státní příspěvkové organizace"**:
       - English: "State Budgetary Organizations".
       - Chinese: "国家预算单位".

    4. **"Územní samosprávný celek"**:
       - English: "Local Government Units" or "Municipalities".
       - Chinese: "地方政府单位" (Never "领土/自治").

    5. **"Běžný účet"**:
       - English: "Current Bank Account" or "Cash at Bank".
       - Chinese: "银行存款".

    6. **"Jmění" (The Net Assets Rule)**:
       - English: "Equity / Net Assets".
       - Chinese: "净资产" or "所有者权益".

    7. **"Ceniny" (The Voucher Rule)**:
       - English: "Cash Equivalents (Vouchers/Stamps)".
       - Chinese: "有价票证" or "有价证券".

    ### 💎 Quality Benchmarks:
    - **Terminology**: English must align with **IPSAS**; Chinese must align with **CAS/GOP** when applicable.
    - **Logic**: Use "Substance over Form". If a Czech term sounds poetic, translate its financial meaning.
    - **Abbreviations**: Provide professional, standardized abbreviations for the short versions to fit database limits.

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


def post_with_backoff(url, headers, payload, extract_fn):
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


def call_openai_compatible(batch_terms, target_langs, api_key, model, base_url, extra_headers=None):
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    if extra_headers:
        headers.update({k: v for k, v in extra_headers.items() if v})

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": build_prompt(batch_terms, target_langs)}],
        "temperature": 0.1,
        "response_format": {"type": "json_object"}
    }
    return post_with_backoff(url, headers, payload, lambda r: json.loads(r.json()['choices'][0]['message']['content']))


def call_provider(batch_terms, target_langs):
    config = PROVIDERS.get(PROVIDER)
    if not config:
        print(f"Unknown provider: {PROVIDER}")
        return None
    return call_openai_compatible(
        batch_terms,
        target_langs,
        api_key=config["api_key"],
        model=config["model"],
        base_url=config["base_url"],
        extra_headers=config.get("extra_headers")
    )


def pick_worker_count(total_terms: int) -> int:
    return max(4, min(MAX_WORKERS, max(4, total_terms // 5)))


def run_batches(terms, cache, batch_size, workers, target_langs, stage_label="main"):
    batches = [terms[i:i + batch_size] for i in range(0, len(terms), batch_size)]
    total_batches = len(batches)
    total_terms = len(terms)
    done_terms = 0
    done_batches = 0
    missing_terms = []

    pbar = None
    if os.environ.get("DISABLE_TQDM") != "1":
        try:
            from tqdm import tqdm
            pbar = tqdm(total=total_terms, desc=f"{stage_label} translation", unit="term", dynamic_ncols=True)
        except Exception:
            pbar = None

    print(f"   -> {stage_label}: threads {workers}, batch size {batch_size}")
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_batch = {executor.submit(call_provider, b, target_langs): b for b in batches}
        for future in as_completed(future_to_batch):
            batch = future_to_batch[future]
            result = future.result()
            if result:
                for k, v in result.items():
                    nk = normalize_term(k)
                    existing = cache.get(nk, {}) if isinstance(cache.get(nk, {}), dict) else {}
                    merged = {**existing, **v}
                    cache[nk] = merged
            for t in batch:
                if normalize_term(t) not in cache:
                    missing_terms.append(t)
            done_batches += 1
            done_terms += len(batch)
            if pbar:
                pbar.update(len(batch))
                pbar.set_postfix_str(f"batch {done_batches}/{total_batches}")
            else:
                print(f"   -> {stage_label} progress: {done_terms}/{total_terms} terms ({done_batches}/{total_batches} batches)", flush=True)

    if pbar:
        with contextlib.suppress(Exception):
            pbar.close()
    return missing_terms


def build_name_smartly(code, cz, trans_data, target_langs):
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

    for keep_count in range(len(lang_entries), 0, -1):
        subset = lang_entries[:keep_count]
        choice_lists = []
        for _, full, short in subset:
            options = []
            if full:
                options.append(full)
            if short and short != full:
                options.append(short)
            if not options:
                options.append(full)
            choice_lists.append(options)

        for combo in product(*choice_lists):
            parts = [cz] + list(combo)
            candidate = f"{code} - " + " / ".join(parts)
            if len(candidate) <= LIMIT:
                return candidate

    return f"{code} - {cz}"[:LIMIT]


def build_output_file(output_dir: str, target_langs) -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    # Use underscore separator for Windows-safe filenames (no pipes)
    langs_label = "_".join(["CZ"] + [code.upper() for code in target_langs]) if target_langs else "CZ"
    fname = f"{OUTPUT_PREFIX}_{langs_label}_{ts}.csv"
    target_dir = output_dir or CURRENT_DIR
    os.makedirs(target_dir, exist_ok=True)
    return os.path.join(target_dir, fname)


def provider_key_missing() -> bool:
    config = PROVIDERS.get(PROVIDER, {})
    return not config.get("api_key")


def process_input(input_file: str, offline: bool = False, output_dir: str = ""):
    print(f"1. 读取输入: {input_file}")
    try:
        all_rows = load_rows_auto(input_file)
    except Exception as e:
        print(str(e))
        return

    valid_rows = []
    unique_names = []
    for row in all_rows:
        if is_current_row(row.get('end_date')):
            valid_rows.append(row)
            name = row.get('polvyk_nazev', '')
            norm_name = normalize_term(name)
            if norm_name:
                unique_names.append(norm_name)

    unique_names = list(dict.fromkeys(unique_names))
    valid_rows.sort(key=lambda x: len((x.get('polvyk') or '')))

    cache = load_cache()
    target_langs = TARGET_LANGS
    translation_requested = bool(target_langs)
    new_terms = []
    if translation_requested:
        for t in list(unique_names):
            entry = cache.get(t)
            if needs_translation_for_langs(entry, target_langs):
                new_terms.append(t)

    if translation_requested and new_terms and not offline:
        total_terms = len(new_terms)
        print(f"\n>>> 🚀 启动翻译({','.join(target_langs)}): {total_terms} 个词条")
        batch_size = BATCH_SIZE
        workers = pick_worker_count(total_terms)

        missing_terms = run_batches(new_terms, cache, batch_size, workers, target_langs, stage_label="首轮")

        retry_round = 1
        while missing_terms and retry_round <= 2:
            print(f"   -> 补偿第{retry_round}轮: {len(missing_terms)} 词条")
            retry_batch_size = min(batch_size, 4)
            retry_workers = min(workers, 4)
            missing_terms = run_batches(missing_terms, cache, retry_batch_size, retry_workers, target_langs, stage_label=f"补偿{retry_round}")
            retry_round += 1

        if missing_terms:
            print(f"   -> 仍缺失 {len(missing_terms)} 词条，需人工检查: {missing_terms}")
        else:
            print("   -> 翻译已全部落库，无遗漏")

        save_cache(cache)
    elif translation_requested and new_terms and offline:
        print(f"\n>>> 🚀 发现 {len(new_terms)} 个新词条，但 offline 模式下跳过翻译({','.join(target_langs)})。它们将以原文写入 CSV。")
    elif not translation_requested:
        print("\n>>> 翻译开关已关闭：仅输出捷克语（cz）到 CSV。")

    print(f"\n2. 生成最终 CSV 文件...")
    csv_rows = [
        ["Account Name", "Parent Account", "Account Number", "Parent Account Number", "Is Group", "Account Type", "Root Type", "Account Currency"],
        [ROOT_ASSET, "", "", "", "1", "", "Asset", CURRENCY],
        [ROOT_LIAB, "", "", "", "1", "", "Liability", CURRENCY],
        [ROOT_EQUITY, "", "", "", "1", "", "Equity", CURRENCY],
        [ROOT_EXP, "", "", "", "1", "Expense Account", "Expense", CURRENCY],
        [ROOT_INC, "", "", "", "1", "Income Account", "Income", CURRENCY],
    ]

    parent_map = {}
    used_account_numbers = set()
    for row in valid_rows:
        vykaz = str(row.get('vykaz', ''))
        polvyk = str(row.get('polvyk', ''))
        name_cz = str(row.get('polvyk_nazev', ''))
        norm_name_cz = normalize_term(name_cz)
        synuc = str(row.get('synuc', ''))

        if vykaz == '3' or not polvyk:
            continue

        root_type, erp_parent = "", ""
        is_asset = False
        is_liab = False

        if vykaz == '1':
            if polvyk.startswith(('PASIVA', 'D.', 'D.I', 'D.II', 'D.III', 'D.IV')):
                root_type, erp_parent = "Liability", ROOT_LIAB
                is_liab = True
            elif polvyk.startswith(('C.', 'C.I', 'C.II', 'C.III')):
                root_type, erp_parent = "Equity", ROOT_EQUITY
            else:
                root_type, erp_parent = "Asset", ROOT_ASSET
                is_asset = True
        elif vykaz == '2':
            if polvyk.startswith(('A.', 'A.I', 'A.II', 'A.III', 'A.IV', 'A.V')):
                root_type, erp_parent = "Expense", ROOT_EXP
            else:
                root_type, erp_parent = "Income", ROOT_INC

        if not root_type:
            continue

        final_acc_num = ""
        if synuc and synuc != '-':
            temp_num = synuc
            if temp_num in used_account_numbers:
                if is_asset:
                    temp_num = f"{synuc}-A"
                elif is_liab:
                    temp_num = f"{synuc}-L"
                else:
                    temp_num = f"{synuc}-1"

            idx = 2
            original_temp = temp_num
            while temp_num in used_account_numbers:
                temp_num = f"{original_temp}-{idx}"
                idx += 1

            final_acc_num = temp_num
            used_account_numbers.add(final_acc_num)

        trans_data = cache.get(norm_name_cz, {})
        group_name = build_name_smartly(polvyk, name_cz, trans_data, target_langs)

        parent_account = ""
        parts = polvyk.rstrip('.').split('.')
        if len(parts) > 1:
            parent_code = ".".join(parts[:-1]) + "."
            parent_account = parent_map.get((vykaz, parent_code))

        if not parent_account:
            parent_account = erp_parent

        csv_rows.append([group_name, parent_account, "", "", "1", "", root_type, CURRENCY])
        parent_map[(vykaz, polvyk)] = group_name

        if synuc and synuc != '-':
            ledger_name = build_name_smartly(final_acc_num, name_cz, trans_data, target_langs)
            csv_rows.append([ledger_name, group_name, final_acc_num, "", "0", "", root_type, CURRENCY])

    output_file = build_output_file(output_dir, target_langs)
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerows(csv_rows)

    print("-" * 30)
    print(f"✅ 完成！生成 {len(csv_rows)-6} 个会计科目")
    print(f"输出文件: {output_file}")
    print("-" * 30)


def parse_args():
    parser = argparse.ArgumentParser(description="Translate Czech COA to ERPNext multilingual CSV")
    parser.add_argument("--input", default=DEFAULT_INPUT_FILE, help="输入文件路径：uctosnova.xml 或 CIS_POLVYK.CSV")
    parser.add_argument("--offline", action="store_true", help="离线模式：跳过 API 调用，缺失翻译将以原文写入")
    parser.add_argument("--output-dir", default="", help="自定义输出目录；默认当前目录")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if TRANSLATE_ENABLED and provider_key_missing() and not args.offline:
        print("⚠️ Missing API key for provider, switching to offline mode (cache/CZ only)")
        args.offline = True
    process_input(input_file=args.input, offline=args.offline, output_dir=args.output_dir)
