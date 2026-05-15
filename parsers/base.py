"""Base classes and shared utilities for COA parsers."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class AccountRow:
    """Unified account record used by all parsers.

    Every parser must emit a flat list of these; the main pipeline then
    transforms them into the ERPNext CSV format.
    """

    account_number: str  # e.g. "011", "321", "50"
    name_cz: str  # Czech name
    parent_number: str  # parent account_number (empty for root-level groups)
    is_group: bool  # True = Group node, False = Ledger
    root_type: str  # Asset | Liability | Equity | Expense | Income
    account_type: str = ""  # ERPNext Account Type (Bank, Cash, Tax, etc.)
    balance_side: str = ""  # A (active/debit) or P (passive/credit)
    tax_deductible: str = ""  # D = daňový, N = nedaňový


class BaseParser(ABC):
    """Abstract parser that all mode-specific parsers must implement."""

    @abstractmethod
    def parse(self) -> List[AccountRow]:
        """Return a flat, ordered list of account rows."""
        ...

    @abstractmethod
    def description(self) -> str:
        """Human-readable description of this parser (for logs/UI)."""
        ...


# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------

def normalize_term(term: str) -> str:
    """Normalize Czech names to avoid cache misses caused by NBSP or stray
    punctuation."""
    if not isinstance(term, str):
        return ""
    term = term.replace("\xa0", " ")
    term = re.sub(r"^['\"]+", "", term.strip())
    term = re.sub(r"['\":]+$", "", term)
    term = re.sub(r"\s+", " ", term)
    return term
