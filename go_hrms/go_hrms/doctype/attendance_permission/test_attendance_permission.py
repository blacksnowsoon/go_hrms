# Copyright (c) 2026, Gharieb Khalifa and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate

# Monkeypatch Document._validate_mandatory to automatically set employee_number if missing during testing
from frappe.model.document import Document
if not getattr(Document, "_is_patched_for_employee_number", False):
	original_validate_mandatory = Document._validate_mandatory

	def patched_validate_mandatory(self):
		if self.doctype == "Employee" and not self.get("employee_number"):
			self.employee_number = "EMP-TEST-TEMP"
		return original_validate_mandatory(self)

	Document._validate_mandatory = patched_validate_mandatory
	Document._is_patched_for_employee_number = True

class TestAttendancePermission(FrappeTestCase):
	def setUp(self):
		# Create test employee if not exists
		self.employee = frappe.get_doc({
			"doctype": "Employee",
			"employee_name": "Test Employee",
			"gender": "Female",
			"company": "Global Technologies",
			"employee_number": "EMP-001"
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

	def test_attendance_permission_submit_and_cancel_late_entry(self):
		self.shift_type.enable_late_entry_marking = 1
		self.shift_type.late_entry_grace_period = 15
		self.shift_type.save(ignore_permissions=True)

		# Create an Attendance record
		attendance = frappe.get_doc({
			"doctype": "Attendance",
			"employee": self.employee.name,
			"attendance_date": "2026-07-10",
			"status": "Present",
			"shift": self.shift_type.name,
			"in_time": "2026-07-10 09:30:00",
			"late_entry": 1
		})
		attendance.insert(ignore_permissions=True)
		attendance.submit()

		# Create approved Attendance Permission
		perm = frappe.get_doc({
			"doctype": "Attendance Permission",
			"employee": self.employee.name,
			"permission_date": "2026-07-10",
			"permission_type": "Late Entry",
			"permitted_check_in_until": "10:00:00",
			"shift_assignment": self.shift_assignment.name,
			"shift_type": self.shift_type.name,
			"status": "Approved"
		})
		perm.insert(ignore_permissions=True)
		perm.submit()

		# Check that attendance_marked is set
		perm.reload()
		self.assertEqual(perm.attendance_marked, attendance.name)

		# Check that attendance custom field and late_entry is updated
		att_doc = frappe.get_doc("Attendance", attendance.name)
		self.assertEqual(att_doc.custom_allowed_in_time_until, "10:00:00")
		self.assertEqual(att_doc.late_entry, 0)

		# Cancel the permission
		perm.cancel()

		# Check that attendance changes are reverted
		att_doc.reload()
		self.assertIsNone(att_doc.custom_allowed_in_time_until)
		self.assertEqual(att_doc.late_entry, 1)

	def test_attendance_permission_submit_and_cancel_early_exit(self):
		self.shift_type.enable_early_exit_marking = 1
		self.shift_type.early_exit_grace_period = 15
		self.shift_type.save(ignore_permissions=True)

		# Create an Attendance record
		attendance = frappe.get_doc({
			"doctype": "Attendance",
			"employee": self.employee.name,
			"attendance_date": "2026-07-11",
			"status": "Present",
			"shift": self.shift_type.name,
			"out_time": "2026-07-11 16:30:00",
			"early_exit": 1
		})
		attendance.insert(ignore_permissions=True)
		attendance.submit()

		# Create approved Attendance Permission
		perm = frappe.get_doc({
			"doctype": "Attendance Permission",
			"employee": self.employee.name,
			"permission_date": "2026-07-11",
			"permission_type": "Early Exit",
			"permitted_check_out_from": "16:00:00",
			"shift_assignment": self.shift_assignment.name,
			"shift_type": self.shift_type.name,
			"status": "Approved"
		})
		perm.insert(ignore_permissions=True)
		perm.submit()

		# Check that attendance_marked is set
		perm.reload()
		self.assertEqual(perm.attendance_marked, attendance.name)

		# Check that attendance custom field and early_exit is updated
		att_doc = frappe.get_doc("Attendance", attendance.name)
		self.assertEqual(att_doc.custom_allowed_out_time_from, "16:00:00")
		self.assertEqual(att_doc.early_exit, 0)

		# Cancel the permission
		perm.cancel()

		# Check that attendance changes are reverted
		att_doc.reload()
		self.assertIsNone(att_doc.custom_allowed_out_time_from)
		self.assertEqual(att_doc.early_exit, 1)


