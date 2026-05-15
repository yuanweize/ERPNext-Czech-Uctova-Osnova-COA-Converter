"""Commercial COA Parser (Decree 500/2002 – Podnikatelé / s.r.o.).

Reads the curated golden-source CSV derived from the Stormware/Pohoda
*uctova_osnova_2024.pdf* and emits ERPNext-compatible AccountRow records.
"""

from __future__ import annotations

import csv
import os
from typing import Dict, List, Optional

from parsers.base import AccountRow, BaseParser

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA_CSV = os.path.join(
    CURRENT_DIR, os.pardir, "data", "commercial", "uctova_osnova_2024.csv"
)

# ---------------------------------------------------------------------------
# Root Type mapping
# ---------------------------------------------------------------------------

# Class → default root type (overridden per-account when A/P markers differ)
_CLASS_ROOT_TYPE: Dict[str, str] = {
    "0": "Asset",
    "1": "Asset",
    "2": "Asset",
    # Class 3: determined per-account by balance_side (A→Asset, P→Liability)
    # Class 4: determined per-group (41-43,49→Equity; 45-48→Liability)
    "5": "Expense",
    "6": "Income",
    "7": "Equity",  # Closing accounts (701/702/710) stored under Equity
}

# Account groups in class 4 that map to Equity
_CLASS4_EQUITY_GROUPS = {"41", "42", "43", "49"}
# Account groups in class 4 that map to Liability
_CLASS4_LIABILITY_GROUPS = {"45", "46", "47", "48"}

# ---------------------------------------------------------------------------
# ERPNext Account Type auto-mapping
# ---------------------------------------------------------------------------

_ACCOUNT_TYPE_MAP: Dict[str, str] = {
    # Cash & Bank
    "211": "Cash",
    "213": "Cash",  # Ceniny (vouchers/stamps) – cash equivalent
    "221": "Bank",
    # Receivable & Payable
    "311": "Receivable",
    "313": "Receivable",
    "314": "Receivable",
    "315": "Receivable",
    "321": "Payable",
    "322": "Payable",
    "324": "Payable",
    "325": "Payable",
    # Tax
    "341": "Tax",
    "342": "Tax",
    "343": "Tax",
    "345": "Tax",
    # Depreciation & Accumulated Depreciation
    "551": "Depreciation",
    # Accumulated depreciation accounts (07x, 08x)
    "071": "Accumulated Depreciation",
    "072": "Accumulated Depreciation",
    "073": "Accumulated Depreciation",
    "074": "Accumulated Depreciation",
    "075": "Accumulated Depreciation",
    "079": "Accumulated Depreciation",
    "081": "Accumulated Depreciation",
    "082": "Accumulated Depreciation",
    "085": "Accumulated Depreciation",
    "086": "Accumulated Depreciation",
    "089": "Accumulated Depreciation",
    # Fixed Asset
    "021": "Fixed Asset",
    "022": "Fixed Asset",
    "025": "Fixed Asset",
    "026": "Fixed Asset",
    "029": "Fixed Asset",
    "031": "Fixed Asset",
    "032": "Fixed Asset",
    # Stock
    "112": "Stock",
    "132": "Stock",
    # Equity
    "411": "Equity",
    "412": "Equity",
    "413": "Equity",
    # Perpetual Inventory defaults
    "389": "Stock Received But Not Billed",
    "518": "Expenses Included In Valuation",
    "549": "Stock Adjustment",
    "563": "Expense Account",
    # Cost of Goods Sold
    "504": "Cost of Goods Sold",
    # Expense accounts (class 5 default)
    "501": "Expense Account",
    "502": "Expense Account",
    "503": "Expense Account",
    "521": "Expense Account",
    # Income accounts (class 6 default)
    "601": "Income Account",
    "602": "Income Account",
    "604": "Income Account",
}


class CommercialParser(BaseParser):
    """Parser for the Czech standard commercial Chart of Accounts (2024).

    The source data is a curated CSV committed to the repository at
    ``data/commercial/uctova_osnova_2024.csv``.
    """

    def __init__(self, csv_path: Optional[str] = None) -> None:
        self._csv_path = csv_path or DEFAULT_DATA_CSV

    def description(self) -> str:
        return (
            "Czech Standard Commercial COA 2024 "
            "(Decree 500/2002 Coll. – Podnikatelé / s.r.o.)"
        )

    # ------------------------------------------------------------------
    # Core parsing
    # ------------------------------------------------------------------

    def parse(self) -> List[AccountRow]:
        raw = self._load_csv()
        rows: List[AccountRow] = []

        for entry in raw:
            acct_num = entry["account_number"].strip()
            name = entry["name_cz"].strip()
            acct_class = entry["account_class"].strip()
            acct_group = entry["account_group"].strip()
            rec_type = entry["type"].strip()  # G / R / V / Z
            bal_side = entry["balance_side"].strip()  # A / P / empty
            tax_ded = entry.get("tax_deductible", "").strip()  # D / N / empty

            # Skip classes 8-9 and off-balance (799)
            if acct_class in ("8", "9"):
                continue
            if acct_num == "799":
                continue

            is_group = rec_type == "G"
            root_type = self._resolve_root_type(acct_num, acct_class, acct_group, bal_side)
            account_type = "" if is_group else _ACCOUNT_TYPE_MAP.get(acct_num, "")

            # Default Account Type for all class 5 / class 6 ledgers
            if not account_type and not is_group:
                if acct_class == "5":
                    account_type = "Expense Account"
                elif acct_class == "6":
                    account_type = "Income Account"

            # Determine parent
            parent_number = self._resolve_parent(acct_num, acct_class, acct_group, is_group)

            rows.append(
                AccountRow(
                    account_number=acct_num,
                    name_cz=name,
                    parent_number=parent_number,
                    is_group=is_group,
                    root_type=root_type,
                    account_type=account_type,
                    balance_side=bal_side,
                    tax_deductible=tax_ded,
                )
            )

        return rows

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_csv(self) -> list:
        path = os.path.normpath(self._csv_path)
        if not os.path.isfile(path):
            raise FileNotFoundError(
                f"Commercial COA data not found: {path}"
            )
        with open(path, "r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            return list(reader)

    @staticmethod
    def _resolve_root_type(
        acct_num: str, acct_class: str, acct_group: str, bal_side: str
    ) -> str:
        # Class 3 – split by A/P marker
        if acct_class == "3":
            return "Asset" if bal_side == "A" else "Liability"

        # Class 4 – split by group
        if acct_class == "4":
            # For the class-level group node "4" itself
            if acct_num == "4":
                return "Equity"
            grp = acct_group[:2] if len(acct_group) >= 2 else acct_num[:2]
            if grp in _CLASS4_EQUITY_GROUPS:
                return "Equity"
            if grp in _CLASS4_LIABILITY_GROUPS:
                return "Liability"
            return "Equity"  # fallback

        # Class 2 – some accounts are passive (short-term borrowings)
        if acct_class == "2" and bal_side == "P":
            return "Liability"

        return _CLASS_ROOT_TYPE.get(acct_class, "Asset")

    @staticmethod
    def _resolve_parent(
        acct_num: str, acct_class: str, acct_group: str, is_group: bool
    ) -> str:
        """Determine the parent account number for tree building.

        Hierarchy: Class (1 digit) → Group (2 digits) → Account (3 digits)
        """
        if len(acct_num) == 1:
            # Top-level class node – parent is empty (will be mapped to ERPNext root)
            return ""
        if len(acct_num) == 2:
            # Group node – parent is class
            return acct_class
        if len(acct_num) == 3:
            # Ledger – parent is group
            return acct_group if acct_group else acct_num[:2]
        return acct_class
