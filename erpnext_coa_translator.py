#!/usr/bin/env python3
"""ERPNext Czech COA Converter – Enterprise-grade dual-mode CLI.

Converts the Czech Chart of Accounts (Účtová osnova) into an ERPNext-ready CSV.
Supports two modes:
  - **commercial** (default): Standard COA for s.r.o. / a.s. (Decree 500/2002)
  - **public_sector**: Government/public-sector COA (Decree 410/2009)

Usage:
    # Commercial (default) – uses built-in 2024 COA data
    python erpnext_coa_translator.py --offline

    # Commercial with translation
    python erpnext_coa_translator.py

    # Public sector – requires input file
    python erpnext_coa_translator.py --mode public_sector --input public_sector_data/uctosnova.xml --offline
"""

from __future__ import annotations

import argparse
import csv
import datetime
import os
import sys
from typing import List

from parsers.base import AccountRow, normalize_term
from parsers.commercial_parser import CommercialParser
from parsers.public_sector_parser import PublicSectorParser
import translation_engine as te

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Currency (overridable via .env)
CURRENCY = os.getenv("CURRENCY", "CZK")
OUTPUT_PREFIX = os.getenv("OUTPUT_PREFIX", "erpnext_coa")

# ERPNext root node names
ROOT_NAMES = {
    "Asset": "Assets - Aktiva",
    "Liability": "Liabilities - Závazky",
    "Equity": "Equity - Vlastní kapitál",
    "Expense": "Expenses - Náklady",
    "Income": "Income - Výnosy",
}


def build_output_file(output_dir: str, target_langs: List[str], mode: str) -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    langs_label = "_".join(["CZ"] + [c.upper() for c in target_langs]) if target_langs else "CZ"
    mode_tag = "commercial" if mode == "commercial" else "public_sector"
    fname = f"{OUTPUT_PREFIX}_{mode_tag}_{langs_label}_{ts}.csv"
    target_dir = output_dir or CURRENT_DIR
    os.makedirs(target_dir, exist_ok=True)
    return os.path.join(target_dir, fname)


def process(mode: str, input_file: str, offline: bool, output_dir: str) -> str:
    """Main processing pipeline."""

    # 1. Select parser
    print(f"━━━ Mode: {mode.upper()} ━━━")
    if mode == "commercial":
        parser = CommercialParser(csv_path=input_file if input_file else None)
    else:
        if not input_file:
            input_file = os.path.join(CURRENT_DIR, "public_sector_data", "uctosnova.xml")
        parser = PublicSectorParser(input_file=input_file)

    print(f"📋 Parser: {parser.description()}")

    # 2. Parse
    print("1. 解析输入数据...")
    rows: List[AccountRow] = parser.parse()
    print(f"   → 解析到 {len(rows)} 个账户条目")

    # 3. Translation
    unique_names = list(dict.fromkeys(
        normalize_term(r.name_cz) for r in rows if normalize_term(r.name_cz)
    ))

    target_langs = te.TARGET_LANGS
    cache = te.translate_terms(unique_names, offline=offline, mode=mode)

    # 4. Build ERPNext CSV
    print("\n2. 生成 ERPNext CSV...")

    csv_rows = [
        ["Account Name", "Parent Account", "Account Number", "Parent Account Number",
         "Is Group", "Account Type", "Root Type", "Account Currency"],
    ]

    # Root nodes
    for rt, name in ROOT_NAMES.items():
        acct_type = ""
        if rt == "Expense":
            acct_type = "Expense Account"
        elif rt == "Income":
            acct_type = "Income Account"
        csv_rows.append([name, "", "", "", "1", acct_type, rt, CURRENCY])

    # Build a lookup: account_number → display name (for parent references)
    acct_display_names = {}

    for row in rows:
        norm = normalize_term(row.name_cz)
        trans_data = cache.get(norm, {})
        display_name = te.build_name(row.account_number, row.name_cz, trans_data, target_langs)
        acct_display_names[row.account_number] = display_name

    # Emit rows
    for row in rows:
        norm = normalize_term(row.name_cz)
        trans_data = cache.get(norm, {})
        display_name = acct_display_names[row.account_number]

        # Resolve parent
        parent_display = ""
        if row.parent_number:
            parent_display = acct_display_names.get(row.parent_number, "")
        if not parent_display:
            # Fall back to ERPNext root
            parent_display = ROOT_NAMES.get(row.root_type, "")

        is_group = "1" if row.is_group else "0"
        acct_num = "" if row.is_group else row.account_number

        csv_rows.append([
            display_name,
            parent_display,
            acct_num,
            "",
            is_group,
            row.account_type,
            row.root_type,
            CURRENCY,
        ])

    # 5. Write output
    output_file = build_output_file(output_dir, target_langs, mode)
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerows(csv_rows)

    total_accounts = len(csv_rows) - 1 - len(ROOT_NAMES)
    print("─" * 40)
    print(f"✅ 完成！生成 {total_accounts} 个会计科目")
    print(f"   输出文件: {output_file}")
    print("─" * 40)
    return output_file


def parse_args():
    parser = argparse.ArgumentParser(
        description="ERPNext Czech COA Converter – Enterprise-grade dual-mode tool"
    )
    parser.add_argument(
        "--mode",
        choices=["commercial", "public_sector"],
        default="commercial",
        help="COA mode: 'commercial' (default, s.r.o./a.s.) or 'public_sector' (gov)",
    )
    parser.add_argument(
        "--input",
        default="",
        help="Input file path. Commercial mode uses built-in data by default. "
             "Public sector mode defaults to public_sector_data/uctosnova.xml.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Skip LLM API calls; missing translations use Czech originals.",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="Custom output directory (default: project root).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if te.TRANSLATE_ENABLED and te.provider_key_missing() and not args.offline:
        print("⚠️ Missing API key → switching to offline mode")
        args.offline = True
    try:
        process(
            mode=args.mode,
            input_file=args.input,
            offline=args.offline,
            output_dir=args.output_dir,
        )
    except Exception as e:
        print(f"❌ {e}")
        sys.exit(1)
