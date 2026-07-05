# Copyright (c) 2026, Gharieb Khalifa and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate

class TestAttendancePermission(FrappeTestCase):
	def setUp(self):
		# Create test employee if not exists
		self.employee = frappe.get_doc({
			"doctype": "Employee",
			"employee_name": "Test Employee",
			"gender": "Female",
			"company": "Global Technologies"
		})
		company = frappe.db.get_value("Company", {}, "name")
		if not company:
			comp_doc = frappe.get_doc({
				"doctype": "Company",
				"company_name": "Test Company",
				"default_currency": "USD"
			}).insert(ignore_permissions=True)
			company = comp_doc.name
		self.employee.company = company
		self.employee.insert(ignore_permissions=True)

		# Create Shift Type
		self.shift_type = frappe.get_doc({
			"doctype": "Shift Type",
			"shift_type_name": "Test Shift Type",
			"start_time": "09:00:00",
			"end_time": "17:00:00"
		}).insert(ignore_permissions=True)

		# Create Shift Assignment
		self.shift_assignment = frappe.get_doc({
			"doctype": "Shift Assignment",
			"employee": self.employee.name,
			"shift_type": self.shift_type.name,
			"start_date": "2026-07-01",
			"status": "Active"
		}).insert(ignore_permissions=True)

		# Set settings
		self.settings = frappe.get_doc("Attendance Permission Settings")
		self.settings.max_permisson_per_month = 2
		self.settings.max_minutes_per_permission = 60
		self.settings.save(ignore_permissions=True)

	def test_max_permissions_per_month_validation(self):
		# Create first approved permission
		perm1 = frappe.get_doc({
			"doctype": "Attendance Permission",
			"employee": self.employee.name,
			"permission_date": "2026-07-01",
			"permission_type": "Late Entry",
			"shift_assignment": self.shift_assignment.name,
			"shift_type": self.shift_type.name,
			"workflow_state": "Approved"
		})
		perm1.insert(ignore_permissions=True)

		# Create second approved permission
		perm2 = frappe.get_doc({
			"doctype": "Attendance Permission",
			"employee": self.employee.name,
			"permission_date": "2026-07-02",
			"permission_type": "Late Entry",
			"shift_assignment": self.shift_assignment.name,
			"shift_type": self.shift_type.name,
			"workflow_state": "Approved"
		})
		perm2.insert(ignore_permissions=True)

		# Create third permission in the same month - should fail validation
		perm3 = frappe.get_doc({
			"doctype": "Attendance Permission",
			"employee": self.employee.name,
			"permission_date": "2026-07-03",
			"permission_type": "Late Entry",
			"shift_assignment": self.shift_assignment.name,
			"shift_type": self.shift_type.name
		})
		
		# Expect frappe.ValidationError
		self.assertRaises(frappe.ValidationError, perm3.insert)

