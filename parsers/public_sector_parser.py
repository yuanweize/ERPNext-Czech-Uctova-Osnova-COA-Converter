"""Public-Sector COA Parser (Decree 410/2009 – Státní pokladna).

This parser handles the legacy data formats (uctosnova.xml and CIS_POLVYK.CSV)
from the Czech State Treasury monitoring system (data.gov.cz).

NOTE: This is the *legacy* parser retained for government / public-sector users.
The default (commercial) parser should be used for s.r.o. / a.s. entities.
"""

from __future__ import annotations

import csv
import os
import re
import xml.etree.ElementTree as ET
from typing import List, Optional

from parsers.base import AccountRow, BaseParser

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_XML = os.path.join(CURRENT_DIR, os.pardir, "public_sector_data", "uctosnova.xml")

# Root node display names (kept identical to legacy output for compatibility)
ROOT_ASSET = "Assets - Aktiva - 资产"
ROOT_LIAB = "Liabilities - Pasiva - 负债"
ROOT_EQUITY = "Equity - Vlastní kapitál - 权益"
ROOT_EXP = "Expenses - Náklady - 费用"
ROOT_INC = "Income - Výnosy - 收入"


def _get_node_text(node, tag_name: str) -> str:
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
    v = v.lstrip("0")
    return v or "0"


def _is_current_row(end_date: str) -> bool:
    s = str(end_date or "")
    return ("9999" in s) or ("99991231" in s)


# ---------------------------------------------------------------------------
# Raw row loaders (XML & CSV)
# ---------------------------------------------------------------------------

def _load_rows_from_xml(input_file: str) -> list:
    try:
        tree = ET.parse(input_file)
        root = tree.getroot()
    except Exception as e:
        raise RuntimeError(f"XML parsing failed: {e}")

    rows = []
    for row in root.findall("row"):
        rows.append(
            {
                "vykaz": _get_node_text(row, "vykaz"),
                "polvyk": _get_node_text(row, "polvyk"),
                "polvyk_nazev": _get_node_text(row, "polvyk_nazev"),
                "synuc": _get_node_text(row, "synuc"),
                "end_date": _get_node_text(row, "end_date"),
                "start_date": _get_node_text(row, "start_date"),
            }
        )
    return rows


def _load_rows_from_csv(input_file: str) -> list:
    rows = []
    with open(input_file, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for r in reader:
            vykaz = _normalize_vykaz(r.get("/BIC/ZC_VYKAZ Výkaz", ""))
            polvyk = (r.get("/BIC/ZC_POLVYK Položka výkazu", "") or "").strip().strip('"')
            synuc = (r.get("/BIC/ZC_SYNUC Syntetický účet", "") or "").strip().strip('"')
            name = (r.get("TXTXL Dlouhý text", "") or "").strip().strip('"')
            datefrom = _date_yyyymmdd_to_ddmmyyyy(r.get("DATEFROM Platí od", ""))
            dateto_raw = (r.get("DATETO Platí do", "") or "").strip().strip('"')
            dateto = _date_yyyymmdd_to_ddmmyyyy(dateto_raw)
            rows.append(
                {
                    "vykaz": vykaz,
                    "polvyk": polvyk,
                    "polvyk_nazev": name,
                    "synuc": synuc,
                    "start_date": datefrom,
                    "end_date": dateto or dateto_raw,
                }
            )
    return rows


def _load_rows_auto(input_file: str) -> list:
    ext = os.path.splitext(input_file)[1].lower()

    def _sniff() -> str:
        try:
            with open(input_file, "rb") as f:
                head = f.read(4096).lstrip()
        except Exception:
            return ""
        return "xml" if head.startswith(b"<") else "csv"

    if ext == ".xml":
        try:
            return _load_rows_from_xml(input_file)
        except Exception:
            return _load_rows_from_csv(input_file)
    if ext == ".csv":
        try:
            return _load_rows_from_csv(input_file)
        except Exception:
            return _load_rows_from_xml(input_file)

    kind = _sniff()
    if kind == "xml":
        return _load_rows_from_xml(input_file)
    if kind == "csv":
        return _load_rows_from_csv(input_file)
    raise RuntimeError(f"Unsupported input type: {input_file}")


class PublicSectorParser(BaseParser):
    """Parser for Czech public-sector COA (Decree 410/2009 Coll.)."""

    def __init__(self, input_file: Optional[str] = None) -> None:
        self._input_file = input_file or DEFAULT_XML

    def description(self) -> str:
        return (
            "Czech Public-Sector COA "
            "(Decree 410/2009 Coll. – Státní pokladna)"
        )

    def parse(self) -> List[AccountRow]:
        all_rows = _load_rows_auto(self._input_file)

        # Filter to current (not expired) rows
        valid_rows = [r for r in all_rows if _is_current_row(r.get("end_date", ""))]
        valid_rows.sort(key=lambda x: len(x.get("polvyk", "") or ""))

        rows: List[AccountRow] = []
        used_numbers: set = set()

        for raw in valid_rows:
            vykaz = str(raw.get("vykaz", ""))
            polvyk = str(raw.get("polvyk", ""))
            name_cz = str(raw.get("polvyk_nazev", ""))
            synuc = str(raw.get("synuc", ""))

            if vykaz == "3" or not polvyk:
                continue

            root_type = ""
            is_asset = False
            is_liab = False

            if vykaz == "1":
                if polvyk.startswith(("PASIVA", "D.", "D.I", "D.II", "D.III", "D.IV")):
                    root_type = "Liability"
                    is_liab = True
                elif polvyk.startswith(("C.", "C.I", "C.II", "C.III")):
                    root_type = "Equity"
                else:
                    root_type = "Asset"
                    is_asset = True
            elif vykaz == "2":
                if polvyk.startswith(("A.", "A.I", "A.II", "A.III", "A.IV", "A.V")):
                    root_type = "Expense"
                else:
                    root_type = "Income"

            if not root_type:
                continue

            # Deduplicate synuc
            final_acc_num = ""
            if synuc and synuc != "-":
                temp = synuc
                if temp in used_numbers:
                    if is_asset:
                        temp = f"{synuc}-A"
                    elif is_liab:
                        temp = f"{synuc}-L"
                    else:
                        temp = f"{synuc}-1"
                idx = 2
                original = temp
                while temp in used_numbers:
                    temp = f"{original}-{idx}"
                    idx += 1
                final_acc_num = temp
                used_numbers.add(final_acc_num)

            # Determine parent
            parent_number = ""
            parts = polvyk.rstrip(".").split(".")
            if len(parts) > 1:
                parent_number = ".".join(parts[:-1]) + "."

            rows.append(
                AccountRow(
                    account_number=final_acc_num or polvyk,
                    name_cz=name_cz,
                    parent_number=parent_number,
                    is_group=not (synuc and synuc != "-"),
                    root_type=root_type,
                    account_type="",
                    balance_side="A" if is_asset else ("P" if is_liab else ""),
                )
            )

        return rows
