# Copyright (c) 2026, Gharieb Khalifa and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from typing import List, Optional
from frappe.utils import getdate

Filters = frappe._dict


def execute(filters: Optional[dict] = None) -> tuple[List[dict], List[dict]]:
	filters = frappe._dict(filters or {})

	if filters.to_date and filters.from_date and filters.to_date <= filters.from_date:
		frappe.throw(_("\"From Date\" can not be greater than or equal to \"To Date\""))

	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns() -> list[dict]:
	columns = [
		{
			"fieldname": "employee",
			"label": _("Employee"),
			"fieldtype": "Link",
			"options": "Employee",
			"width": 120,
		},
		{
			"fieldname": "employee_name",
			"label": _("Employee Name"),
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"fieldname": "department",
			"label": _("Department"),
			"fieldtype": "Link",
			"options": "Department",
			"width": 140,
		},
		{
			"fieldname": "designation",
			"label": _("Designation"),
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"fieldname": "permission_type",
			"label": _("Permission Type"),
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"fieldname": "permission_date",
			"label": _("Permission Date"),
			"fieldtype": "Date",
			"width": 110,
		},
		{
			"fieldname": "status",
			"label": _("Status"),
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"fieldname": "total",
			"label": _("Total"),
			"fieldtype": "Int",
			"width": 80,
		},
	]
	return columns


def get_data(filters: Filters) -> list[dict]:
	AP = frappe.qb.DocType("Attendance Permission")
	Employee = frappe.qb.DocType("Employee")

	query = (
		frappe.qb.from_(AP)
		.join(Employee)
		.on(AP.employee == Employee.name)
		.select(
			AP.employee,
			AP.employee_name,
			AP.department,
			Employee.designation,
			AP.permission_type,
			AP.permission_date,
			AP.status,
		)
		.where(AP.docstatus != 2)  # exclude cancelled
	)

	# Date range filter
	if filters.get("from_date"):
		query = query.where(AP.permission_date >= getdate(filters.from_date))
	if filters.get("to_date"):
		query = query.where(AP.permission_date <= getdate(filters.to_date))

	# Other filters
	if filters.get("company"):
		query = query.where(AP.company == filters.company)
	if filters.get("department"):
		query = query.where(AP.department == filters.department)
	if filters.get("employee"):
		query = query.where(AP.employee == filters.employee)
	if filters.get("permission_type"):
		query = query.where(AP.permission_type == filters.permission_type)
	if filters.get("employee_status"):
		query = query.where(Employee.status == filters.employee_status)

	query = query.orderby(AP.employee).orderby(AP.permission_date)

	records = query.run(as_dict=True)

	# Compute summary totals per employee+permission_type
	from collections import defaultdict

	totals: dict = defaultdict(int)
	for row in records:
		totals[(row.employee, row.permission_type)] += 1

	data = []
	seen: set = set()

	for row in records:
		key = (row.employee, row.permission_type)
		row["total"] = totals[key]
		data.append(row)

	return data


def get_employees(filters: Filters) -> list[dict]:
	Employee = frappe.qb.DocType("Employee")
	query = frappe.qb.from_(Employee).select(
		Employee.name,
		Employee.employee_name,
		Employee.department,
		Employee.designation,
	)
	for field in ["company", "department"]:
		if filters.get(field):
			query = query.where(getattr(Employee, field) == filters.get(field))

	if filters.get("employee"):
		query = query.where(Employee.name == filters.get("employee"))

	if filters.get("employee_status"):
		query = query.where(Employee.status == filters.get("employee_status"))

	return query.run(as_dict=True)