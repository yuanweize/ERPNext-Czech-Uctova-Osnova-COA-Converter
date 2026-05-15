# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import csv
import os
from functools import reduce

import frappe
from frappe import _
from frappe.desk.form.linked_with import get_linked_fields
from frappe.model.document import Document
from frappe.utils import cint, cstr
from frappe.utils.csvutils import UnicodeWriter
from frappe.utils.xlsxutils import (
	read_xls_file_from_attached_file,
	read_xlsx_file_from_attached_file,
)

from erpnext.accounts.doctype.account.chart_of_accounts.chart_of_accounts import (
	build_tree_from_json,
	create_charts,
)


class ChartofAccountsImporter(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		company: DF.Link | None
		import_file: DF.Attach | None
	# end: auto-generated types

	def validate(self):
		if self.import_file:
			get_coa("Chart of Accounts Importer", "All Accounts", file_name=self.import_file, for_validate=1)


def validate_columns(data):
	if not data:
		frappe.throw(_("No data found. Seems like you uploaded a blank file"))

	no_of_columns = max([len(d) for d in data])

	if no_of_columns != 8:
		frappe.throw(
			_(
				"Columns are not according to template. Please compare the uploaded file with standard template"
			),
			title=(_("Wrong Template")),
		)


@frappe.whitelist()
def validate_company(company):
	parent_company, allow_account_creation_against_child_company = frappe.get_cached_value(
		"Company", company, ["parent_company", "allow_account_creation_against_child_company"]
	)

	if parent_company and (not allow_account_creation_against_child_company):
		msg = _("{} is a child company.").format(frappe.bold(company)) + " "
		msg += _("Please import accounts against parent company or enable {} in company master.").format(
			frappe.bold(_("Allow Account Creation Against Child Company"))
		)
		frappe.throw(msg, title=_("Wrong Company"))

	if frappe.db.get_all("GL Entry", {"company": company}, "name", limit=1):
		return False


@frappe.whitelist()
def import_coa(file_name, company):
	# delete existing data for accounts
	unset_existing_data(company)

	# create accounts
	file_doc, extension = get_file(file_name)

	if extension == "csv":
		data = generate_data_from_csv(file_doc)
	else:
		data = generate_data_from_excel(file_doc, extension)

	frappe.local.flags.ignore_root_company_validation = True
	forest = build_forest(data)
	create_charts(company, custom_chart=forest, from_coa_importer=True)

	# trigger on_update for company to reset default accounts
	set_default_accounts(company)


def get_file(file_name):
	file_doc = frappe.get_doc("File", {"file_url": file_name})
	parts = file_doc.get_extension()
	extension = parts[1]
	extension = extension.lstrip(".")

	if extension not in ("csv", "xlsx", "xls"):
		frappe.throw(
			_(
				"Only CSV and Excel files can be used to for importing data. Please check the file format you are trying to upload"
			)
		)

	return file_doc, extension


def generate_data_from_csv(file_doc, as_dict=False):
	"""read csv file and return the generated nested tree"""

	file_path = file_doc.get_full_path()

	data = []
	with open(file_path) as in_file:
		csv_reader = list(csv.reader(in_file))
		headers = csv_reader[0]
		del csv_reader[0]  # delete top row and headers row

		for row in csv_reader:
			if as_dict:
				data.append({frappe.scrub(header): row[index] for index, header in enumerate(headers)})
			else:
				if not row[1] and len(row) > 1:
					row[1] = row[0]
					row[3] = row[2]
				data.append(row)

	# convert csv data
	return data


def generate_data_from_excel(file_doc, extension, as_dict=False):
	content = file_doc.get_content()

	if extension == "xlsx":
		rows = read_xlsx_file_from_attached_file(fcontent=content)
	elif extension == "xls":
		rows = read_xls_file_from_attached_file(content)

	data = []
	headers = rows[0]
	del rows[0]

	for row in rows:
		if as_dict:
