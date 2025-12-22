import xml.etree.ElementTree as ET
import csv
import os
import json
import time
import re
import argparse
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import contextlib
from dotenv import load_dotenv

load_dotenv()

# ================= 配置区域（可被 .env 覆盖） =================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# 1. SiliconFlow API Key
SILICONFLOW_API_KEY =  os.getenv("SILICONFLOW_API_KEY", "")

# 2. 模型选择
MODEL_ID = os.getenv("MODEL_ID", "Qwen/Qwen2.5-72B-Instruct")

# 3. 并发数量 (动态上限)
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "16"))

# 3b. 单批翻译的词条数量
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "8"))

# 4. 货币
CURRENCY = os.getenv("CURRENCY", "CZK")

# 5. 数据库限制 (ERPNext ID 限制)
LIMIT = int(os.getenv("LIMIT", "131"))

# 6. 输出前缀（文件名会自动加时间戳到分钟）
OUTPUT_PREFIX = os.getenv("OUTPUT_PREFIX", "erpnext_coa_multilingual")

# 数据文件路径
INPUT_FILE = os.path.join(CURRENT_DIR, 'uctosnova.xml')
CACHE_FILE = os.path.join(CURRENT_DIR, 'translation_cache.json')
SECONDARY_CACHE_FILE = os.path.join(CURRENT_DIR, 'translation_cache_Qwen', 'translation_cache.json')

# --- 根节点名称 ---
ROOT_ASSET  = "Assets - Aktiva - 资产"
ROOT_LIAB   = "Liabilities - Pasiva - 负债"
ROOT_EQUITY = "Equity - Vlastní kapitál - 权益"
ROOT_EXP    = "Expenses - Náklady - 费用"
ROOT_INC    = "Income - Výnosy - 收入"

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
                # keep the first occurrence if duplicates collapse after normalization
                normalized_cache.setdefault(nk, v)

            # 尝试从备用缓存补齐缺失（例如历史翻译文件）
            if os.path.exists(SECONDARY_CACHE_FILE):
                try:
                    with open(SECONDARY_CACHE_FILE, 'r', encoding='utf-8') as f2:
                        secondary_raw = json.load(f2)
                    for k, v in secondary_raw.items():
                        nk = normalize_term(k)
                        normalized_cache.setdefault(nk, v)
                except: pass

            if changed:
                save_cache(normalized_cache)
            return normalized_cache
        except: return {}
    return {}

def save_cache(cache):
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def call_siliconflow_api(batch_terms):
    url = "https://api.siliconflow.cn/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = f"""

    Role: You are a Lead Partner at a Big 4 firm and a former consultant for the Czech Ministry of Finance.

    You are the world's leading expert in Decree No. 410/2009 Coll. (Czech Public Sector Accounting).


    Task: Map Czech Governmental Chart of Accounts to IPSAS/IFRS and Chinese Accounting Standards (CAS/ASBE).


    ### 🚨 THE "UNBREAKABLE" RULES (Failure = Immediate Project Rejection):


    1. **"Cizí zdroje" (Fundamental Identity)**:

       - IT IS THE LIABILITIES SIDE OF THE BALANCE SHEET.

       - English: MUST be "Liabilities" (NEVER "Resources").

       - Chinese: MUST be "负债" (NEVER "外来资源").


    2. **"Rezervy" in Liabilities (The Provision Rule)**:

       - In this context, it is a liability for future obligations.

       - English: "Provisions" (Never "Reserves").

       - Chinese: "预计负债" or "准备金".


    3. **"Územní samosprávné celky (ÚSC)" (The Municipality Rule)**:

       - English: "Local Government Units" or "Municipalities".

       - Chinese: "地方政府单位". (Never "领土/自治").


    4. **"Organizační složky státu (OSS)" (The Budgetary Rule)**:

       - English: "State Budgetary Organizations".

       - Chinese: "国家预算单位". (Never "组织单位").


    5. **"Běžný účet" (The Cash Rule)**:

       - English: "Current Bank Account" or "Cash at Bank".

       - Chinese: "银行存款".


    6. **"Jmění" (The Net Assets Rule)**:

       - English: "Equity / Net Assets".

       - Chinese: "净资产" or "所有者权益".


    7. **"Ceniny" (The Voucher Rule)**:

       - English: "Cash Equivalents (Vouchers/Stamps)".

       - Chinese: "有价票证" or "有价证券".


    ### 💎 Quality Benchmarks:

    - **Terminology**: English must align with **IPSAS** (International Public Sector Accounting Standards). Chinese must align with **CAS (中国企业会计准则)** for commercial logic and **GOP (政府会计准则)** for entity logic.

    - **Logic**: Use "Substance over Form". If a Czech term sounds poetic, translate it to its cold, hard financial meaning.

    - **Abbreviations**: Create professional, standardized abbreviations for the 'short' versions to fit database limits.

      - EN: Use "Accum.", "Depr.", "PPE", "Acct.", "Prov.", "L/T", "S/T".

      - ZH: 使用行业黑话，如 "长期股权投资"->"长投", "累计折旧"->"累折", "应付账款"->"应付", "其他应收款"->"其他应收".


    ### 📥 Input Data:

    {json.dumps(batch_terms, ensure_ascii=False)}


    ### 📤 Output Format (Strict JSON):

    {{

        "Czech Original": {{

            "en_full": "Formal IPSAS/IFRS Name",

            "en_short": "Standard Audit Abbreviation",

            "zh_full": "标准会计准则全称",

            "zh_short": "专业会计简称"

        }}

    }}

    """ 

    data = {
        "model": MODEL_ID,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "response_format": { "type": "json_object" }
    }

    backoff = 2
    for attempt in range(6):
        try:
            response = requests.post(url, headers=headers, data=json.dumps(data), timeout=60)
            if response.status_code == 200:
                content = response.json()['choices'][0]['message']['content']
                return json.loads(content)
            # 对 429/5xx 做指数回退
            if response.status_code in (429, 500, 502, 503, 504):
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)
                continue
            # 其他错误直接跳过
        except Exception:
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)
    return None

def pick_worker_count(total_terms: int) -> int:
    # 词条少就少开线程，最多不超过 MAX_WORKERS
    return max(4, min(MAX_WORKERS, max(4, total_terms // 5)))

def run_batches(terms, cache, batch_size, workers, stage_label="首轮"):
    batches = [terms[i:i + batch_size] for i in range(0, len(terms), batch_size)]
    total_batches = len(batches)
    total_terms = len(terms)
    done_terms = 0
    done_batches = 0
    missing_terms = []

    # tqdm 进度条（可选，未安装则用文本回退；可用环境变量 DISABLE_TQDM=1 关闭）
    pbar = None
    if os.environ.get("DISABLE_TQDM") != "1":
        try:
            from tqdm import tqdm
            pbar = tqdm(total=total_terms, desc=f"{stage_label} 翻译", unit="term", dynamic_ncols=True)
        except Exception:
            pbar = None

    print(f"   -> {stage_label}: 分配线程 {workers}，批大小 {batch_size}")
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_batch = {executor.submit(call_siliconflow_api, b): b for b in batches}
        for future in as_completed(future_to_batch):
            batch = future_to_batch[future]
            result = future.result()
            if result:
                for k, v in result.items():
                    cache[normalize_term(k)] = v
            # 标记这一批中仍未落库的词条
            for t in batch:
                if normalize_term(t) not in cache:
                    missing_terms.append(t)
            done_batches += 1
            done_terms += len(batch)
            if pbar:
                pbar.update(len(batch))
                pbar.set_postfix_str(f"批 {done_batches}/{total_batches}")
            else:
                print(f"   -> {stage_label}进度: 已完成 {done_terms}/{total_terms} 词条 ({done_batches}/{total_batches} 批)", flush=True)

    if pbar:
        with contextlib.suppress(Exception):
            pbar.close()
    return missing_terms

def build_name_smartly(code, cz, trans_data):
    en_full = trans_data.get('en_full', "")
    zh_full = trans_data.get('zh_full', "")
    if not trans_data or not en_full or en_full == cz:
        return f"{code} - {cz}"[:LIMIT]

    en_short = trans_data.get('en_short', en_full)
    zh_short = trans_data.get('zh_short', zh_full)

    # 1. 三语全称
    v1 = f"{code} - {cz} / {en_full} / {zh_full}"
    if len(v1) <= LIMIT: return v1

    # 2. 中文精简
    v2 = f"{code} - {cz} / {en_full} / {zh_short}"
    if len(v2) <= LIMIT: return v2

    # 3. 双语精简
    v3 = f"{code} - {cz} / {en_short} / {zh_short}"
    if len(v3) <= LIMIT: return v3

    # 4. 弃中保英全
    v4 = f"{code} - {cz} / {en_full}"
    if len(v4) <= LIMIT: return v4

    # 5. 弃中保英简
    v5 = f"{code} - {cz} / {en_short}"
    if len(v5) <= LIMIT: return v5

    return f"{code} - {cz}"[:LIMIT]

def build_output_file(output_dir: str) -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    fname = f"{OUTPUT_PREFIX}_{ts}.csv"
    target_dir = output_dir or CURRENT_DIR
    os.makedirs(target_dir, exist_ok=True)
    return os.path.join(target_dir, fname)


def process_xml(offline: bool = False, output_dir: str = ""):
    print(f"1. 读取 XML: {INPUT_FILE}")
    try:
        tree = ET.parse(INPUT_FILE)
        root = tree.getroot()
    except Exception as e:
        print(f"XML 解析失败: {e}")
        return

    valid_rows = []
    unique_names = []
    for row in root.findall('row'):
        if '9999' in str(get_node_text(row, 'end_date')):
            valid_rows.append(row)
            name = get_node_text(row, 'polvyk_nazev')
            norm_name = normalize_term(name)
            if norm_name: unique_names.append(norm_name)

    # 去重，避免重复翻译
    unique_names = list(dict.fromkeys(unique_names))
    
    valid_rows.sort(key=lambda x: len(get_node_text(x, 'polvyk')))

    cache = load_cache()
    new_terms = [t for t in list(unique_names) if t not in cache]
    
    if new_terms and not offline:
        total_terms = len(new_terms)
        print(f"\n>>> 🚀 启动翻译: {total_terms} 个词条")
        batch_size = BATCH_SIZE
        workers = pick_worker_count(total_terms)

        missing_terms = run_batches(new_terms, cache, batch_size, workers, stage_label="首轮")

        # 补偿重试（最多两轮），避免出现“未报错但有遗漏”
        retry_round = 1
        while missing_terms and retry_round <= 2:
            print(f"   -> 补偿第{retry_round}轮: {len(missing_terms)} 词条")
            retry_batch_size = min(batch_size, 4)
            retry_workers = min(workers, 4)
            missing_terms = run_batches(missing_terms, cache, retry_batch_size, retry_workers, stage_label=f"补偿{retry_round}")
            retry_round += 1

        if missing_terms:
            print(f"   -> 仍缺失 {len(missing_terms)} 词条，需人工检查: {missing_terms}")
        else:
            print("   -> 翻译已全部落库，无遗漏")

        save_cache(cache)
    elif new_terms and offline:
        print(f"\n>>> 🚀 发现 {len(new_terms)} 个新词条，但 offline 模式下跳过翻译。它们将以原文写入 CSV。")

    print(f"\n2. 生成最终 CSV 文件...")
    csv_rows = [
        ["Account Name", "Parent Account", "Account Number", "Parent Account Number", "Is Group", "Account Type", "Root Type", "Account Currency"],
        [ROOT_ASSET,  "", "", "", "1", "", "Asset", CURRENCY],
        [ROOT_LIAB,   "", "", "", "1", "", "Liability", CURRENCY],
        [ROOT_EQUITY, "", "", "", "1", "", "Equity", CURRENCY],
        [ROOT_EXP,    "", "", "", "1", "Expense Account", "Expense", CURRENCY],
        [ROOT_INC,    "", "", "", "1", "Income Account", "Income", CURRENCY],
    ]

    parent_map = {}
    used_account_numbers = set() # <--- 新增：用于追踪已使用的科目编号
    count = 0

    for row in valid_rows:
        vykaz = get_node_text(row, 'vykaz')
        polvyk = get_node_text(row, 'polvyk')
        name_cz = get_node_text(row, 'polvyk_nazev')
        norm_name_cz = normalize_term(name_cz)
        synuc = get_node_text(row, 'synuc')

        if vykaz == '3' or not polvyk: continue

        # 确定根类型
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
        
        if not root_type: continue

        # ==============================================================================
        # 🔑 处理 Account Number 的唯一性逻辑 (解决 248 冲突)
        # ==============================================================================
        final_acc_num = ""
        if synuc and synuc != '-':
            temp_num = synuc
            # 如果编号已经用过，且当前是资产或负债端，加上后缀区分
            if temp_num in used_account_numbers:
                if is_asset: temp_num = f"{synuc}-A"
                elif is_liab: temp_num = f"{synuc}-L"
                else: temp_num = f"{synuc}-1" # 其他情况加数字
            
            # 如果加了后缀还冲突(极端情况)，继续加后缀直至唯一
            idx = 2
            original_temp = temp_num
            while temp_num in used_account_numbers:
                temp_num = f"{original_temp}-{idx}"
                idx += 1
            
            final_acc_num = temp_num
            used_account_numbers.add(final_acc_num)

        # 获取翻译并构建名称
        trans_data = cache.get(norm_name_cz, {})
        group_name = build_name_smartly(polvyk, name_cz, trans_data)
        
        # 寻找父级
        parent_account = ""
        parts = polvyk.rstrip('.').split('.')
        if len(parts) > 1:
            parent_code = ".".join(parts[:-1]) + "."
            parent_account = parent_map.get((vykaz, parent_code))
        
        if not parent_account: parent_account = erp_parent

        # 写入组
        csv_rows.append([group_name, parent_account, "", "", "1", "", root_type, CURRENCY])
        parent_map[(vykaz, polvyk)] = group_name
        count += 1

        # 写入科目 (Ledger)
        if synuc and synuc != '-':
            ledger_name = build_name_smartly(final_acc_num, name_cz, trans_data)
            csv_rows.append([ledger_name, group_name, final_acc_num, "", "0", "", root_type, CURRENCY])
            count += 1

    output_file = build_output_file(output_dir)
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerows(csv_rows)

    print("-" * 30)
    print(f"✅ 完成！已自动处理重复编号 (如 248 -> 248-A / 248-L)")
    print(f"输出文件: {output_file}")
    print("-" * 30)

def parse_args():
    parser = argparse.ArgumentParser(description="Translate Czech COA to ERPNext multilingual CSV")
    parser.add_argument("--offline", action="store_true", help="离线模式：跳过 API 调用，缺失翻译将以原文写入")
    parser.add_argument("--output-dir", default="", help="自定义输出目录；默认当前目录")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if not SILICONFLOW_API_KEY and not args.offline:
        print("⚠️ 未找到 SILICONFLOW_API_KEY，自动切换 offline 模式（仅使用缓存或原文）")
        args.offline = True
    process_xml(offline=args.offline, output_dir=args.output_dir)