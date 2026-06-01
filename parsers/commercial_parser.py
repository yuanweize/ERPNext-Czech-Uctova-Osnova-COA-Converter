"""Commercial COA Parser (Decree 500/2002 – Podnikatelé / s.r.o.).

Reads the curated golden-source CSV derived from the Stormware/Pohoda
*uctova_osnova_2024.pdf* and emits ERPNext-compatible AccountRow records.

Key design decisions (IFRS-aligned):
  - Root Type is determined primarily by the CSV ``balance_side`` column
    (A → Asset, P → Liability) for leaf accounts, combined with group-level
    classification for Class 4 (Equity vs Liability).
  - Mixed classes (2, 3, 4) are split: groups whose accounts all share the
    same balance side stay as groups under the correct root.  Groups with
    mixed A/P children are split – the majority determines the group's root
    and minority accounts are re-parented directly under the correct ERPNext
    root node.
  - Class-level nodes for mixed classes (2, 3, 4) are **not emitted** because
    a single node cannot carry two Root Types in ERPNext's tree.
"""

from __future__ import annotations

import csv
import os
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Set, Tuple

from parsers.base import AccountRow, BaseParser

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA_CSV = os.path.join(
    CURRENT_DIR, os.pardir, "data", "commercial", "uctova_osnova_2024.csv"
)

# ---------------------------------------------------------------------------
# Root Type constants
# ---------------------------------------------------------------------------

# Pure (non-mixed) class → root type
_PURE_CLASS_ROOT_TYPE: Dict[str, str] = {
    "0": "Asset",
    "1": "Asset",
    "5": "Expense",
    "6": "Income",
    "7": "Equity",  # Closing accounts (701/702/710) stored under Equity
}

# Classes that contain a mix of Asset/Liability/Equity and need splitting
_MIXED_CLASSES: Set[str] = {"2", "3", "4"}

# Class 4 group → root type (hard rule per Czech accounting law)
_CLASS4_EQUITY_GROUPS: Set[str] = {"41", "42", "43", "49"}
_CLASS4_LIABILITY_GROUPS: Set[str] = {"45", "46", "47", "48"}

# Class 2 groups that are purely Liability (short-term borrowings)
_CLASS2_LIABILITY_GROUPS: Set[str] = {"23", "24"}

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

        # Phase 1: collect all entries and build group→children mapping
        entries: List[dict] = []
        group_children: Dict[str, List[str]] = defaultdict(list)
        # Map: acct_num → balance_side for leaf accounts
        leaf_bal_side: Dict[str, str] = {}

        for entry in raw:
            acct_num = entry["account_number"].strip()
            acct_class = entry["account_class"].strip()
            acct_group = entry["account_group"].strip()
            rec_type = entry["type"].strip()  # G / R / V / Z
            bal_side = entry["balance_side"].strip()  # A / P / empty

            # Skip classes 8-9
            if acct_class in ("8", "9"):
                continue

            entries.append(entry)

            # Track balance_side for leaf accounts (non-group)
            if rec_type != "G" and bal_side:
                leaf_bal_side[acct_num] = bal_side
                # Register under its group
                grp = acct_group if acct_group else acct_num[:2]
                group_children[grp].append(acct_num)

        # Phase 2: determine majority root type for each mixed group
        group_root_type = self._compute_group_root_types(
            group_children, leaf_bal_side
        )

        # Phase 3: build rows with correct root_type and parent routing
        rows: List[AccountRow] = []
        for entry in entries:
            acct_num = entry["account_number"].strip()
            name = entry["name_cz"].strip()
            acct_class = entry["account_class"].strip()
            acct_group = entry["account_group"].strip()
            rec_type = entry["type"].strip()
            bal_side = entry["balance_side"].strip()
            tax_ded = entry.get("tax_deductible", "").strip()

            is_group = rec_type == "G"

            # Skip class-level nodes for mixed classes – they cannot
            # carry a single Root Type in ERPNext's tree structure.
            if len(acct_num) == 1 and acct_class in _MIXED_CLASSES:
                continue

            # Resolve root type
            root_type = self._resolve_root_type(
                acct_num, acct_class, acct_group, bal_side,
                group_root_type, leaf_bal_side
            )

            # Resolve account type
            account_type = "" if is_group else _ACCOUNT_TYPE_MAP.get(acct_num, "")
            if not account_type and not is_group:
                if acct_class == "5":
                    account_type = "Expense Account"
                elif acct_class == "6":
                    account_type = "Income Account"

            # Resolve parent (handles mixed-class splitting)
            parent_number = self._resolve_parent(
                acct_num, acct_class, acct_group, is_group,
                root_type, group_root_type
            )

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
    def _compute_group_root_types(
        group_children: Dict[str, List[str]],
        leaf_bal_side: Dict[str, str],
    ) -> Dict[str, str]:
        """Determine the root type for each 2-digit group.

        For Class 4 groups the mapping is fixed by law.
        For Class 2 groups 23/24 the mapping is fixed (Liability).
        For Class 3 mixed groups, the majority balance_side wins.
        """
        result: Dict[str, str] = {}

        for grp, children in group_children.items():
            grp_class = grp[0] if grp else ""

            # Class 4: fixed mapping by group
            if grp_class == "4":
                if grp in _CLASS4_EQUITY_GROUPS:
                    result[grp] = "Equity"
                elif grp in _CLASS4_LIABILITY_GROUPS:
                    result[grp] = "Liability"
                else:
                    result[grp] = "Equity"  # fallback
                continue

            # Class 2: 23/24 are Liability, rest are Asset
            if grp_class == "2":
                if grp in _CLASS2_LIABILITY_GROUPS:
                    result[grp] = "Liability"
                else:
                    result[grp] = "Asset"
                continue

            # Class 0, 1: always Asset
            if grp_class in ("0", "1"):
                result[grp] = "Asset"
                continue

            # Class 5: always Expense
            if grp_class == "5":
                result[grp] = "Expense"
                continue

            # Class 6: always Income
            if grp_class == "6":
                result[grp] = "Income"
                continue

            # Class 7: Equity
            if grp_class == "7":
                result[grp] = "Equity"
                continue

            # Class 3: determine by majority of balance_side
            if grp_class == "3":
                sides = [leaf_bal_side.get(c, "") for c in children]
                counts = Counter(sides)
                a_count = counts.get("A", 0)
                p_count = counts.get("P", 0)
                # Majority wins; tie → Liability (conservative)
                result[grp] = "Asset" if a_count > p_count else "Liability"
                continue

            # Fallback
            result[grp] = "Asset"

        return result

    @staticmethod
    def _resolve_root_type(
        acct_num: str,
        acct_class: str,
        acct_group: str,
        bal_side: str,
        group_root_type: Dict[str, str],
        leaf_bal_side: Dict[str, str],
    ) -> str:
        """Determine ERPNext Root Type for a single account.

        Priority:
        1. Pure classes (0,1,5,6,7) → fixed mapping
        2. Class 4 → by group (Equity or Liability)
        3. Class 2 → by group (23/24→Liability, rest→Asset), override by
           leaf balance_side for individual accounts
        4. Class 3 → by leaf balance_side (A→Asset, P→Liability)
        5. Group/class nodes in mixed classes → by computed group root type
        """
        # --- Pure classes ---
        if acct_class in _PURE_CLASS_ROOT_TYPE:
            return _PURE_CLASS_ROOT_TYPE[acct_class]

        # --- Class 4 ---
        if acct_class == "4":
            if len(acct_num) == 1:
                # Class-level node "4" — not emitted, but just in case
                return "Equity"
            grp = acct_group[:2] if len(acct_group) >= 2 else acct_num[:2]
            if grp in _CLASS4_EQUITY_GROUPS:
                return "Equity"
            if grp in _CLASS4_LIABILITY_GROUPS:
                return "Liability"
            return "Equity"

        # --- Class 2 ---
        if acct_class == "2":
            # Leaf with explicit balance_side
            if bal_side == "P":
                return "Liability"
            if bal_side == "A":
                return "Asset"
            # Group node
            if len(acct_num) == 1:
                return "Asset"  # class-level node — not emitted for mixed
            grp = acct_group[:2] if len(acct_group) >= 2 else acct_num[:2]
            return group_root_type.get(grp, "Asset")

        # --- Class 3 ---
        if acct_class == "3":
            # Leaf with explicit balance_side
            if bal_side == "A":
                return "Asset"
            if bal_side == "P":
                return "Liability"
            # Group node: use computed group majority
            if len(acct_num) == 1:
                return "Asset"  # class-level — not emitted
            grp = acct_group[:2] if len(acct_group) >= 2 else acct_num[:2]
            return group_root_type.get(grp, "Asset")

        return "Asset"  # fallback

    @staticmethod
    def _resolve_parent(
        acct_num: str,
        acct_class: str,
        acct_group: str,
        is_group: bool,
        root_type: str,
        group_root_type: Dict[str, str],
    ) -> str:
        """Determine the parent account number for tree building.

        For pure classes: Class (1 digit) → Group (2 digits) → Account (3 digits)
        For mixed classes (2, 3, 4): class-level nodes are skipped; groups
        become direct children of the ERPNext root.  Leaf accounts whose
        root_type differs from their group's root_type are re-parented
        directly under the ERPNext root (parent_number = "").
        """
        # --- Pure classes (0, 1, 5, 6, 7) ---
        if acct_class not in _MIXED_CLASSES:
            if len(acct_num) == 1:
                # Class node → child of ERPNext root
                return ""
            if len(acct_num) == 2:
                # Group node → child of class node
                return acct_class
            if len(acct_num) == 3:
                # Leaf → child of group
                return acct_group if acct_group else acct_num[:2]
            return acct_class

        # --- Mixed classes (2, 3, 4): skip class-level node ---

        if len(acct_num) == 1:
            # Class-level group node for mixed class — still emitted but
            # we won't emit it (handled in parse()); if it slips through,
            # parent is ERPNext root
            return ""

        if len(acct_num) == 2:
            # Group node in mixed class → direct child of ERPNext root
            # (no class-level intermediate)
            return ""

        if len(acct_num) == 3:
            # Leaf in mixed class.
            # Check if its root_type matches the group's root_type.
            grp = acct_group if acct_group else acct_num[:2]
            grp_rt = group_root_type.get(grp, "")

            if grp_rt == root_type:
                # Matches → child of group as normal
                return grp
            else:
                # Minority: root_type differs from group → re-parent
                # directly under ERPNext root (parent = "")
                return ""

        return ""
