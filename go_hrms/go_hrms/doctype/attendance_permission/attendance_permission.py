# Copyright (c) 2026, Gharieb Khalifa and contributors
# For license information, please see license.txt

import datetime
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class AttendancePermission(Document):
	def validate(self):
		self.validate_max_permissions_per_month()

	def validate_max_permissions_per_month(self):
		if not self.employee or not self.permission_date:
			return

		# Load settings
		max_allowed = frappe.db.get_single_value("Attendance Permission Settings", "max_permisson_per_month")
		if not max_allowed:
			return

		# Find the start and end of the month of the permission date
		date = getdate(self.permission_date)
		start_date = date.replace(day=1)
		
		if start_date.month == 12:
			end_date = datetime.date(start_date.year, 12, 31)
		else:
			end_date = datetime.date(start_date.year, start_date.month + 1, 1) - datetime.timedelta(days=1)

		# Count approved permissions
		approved_count = frappe.db.count("Attendance Permission", filters={
			"employee": self.employee,
			"workflow_state": "Approved",
			"permission_date": ["between", [start_date, end_date]],
			"name": ["!=", self.name]
		})

		if approved_count >= max_allowed:
			frappe.throw(
				_("Employee {0} has already reached the maximum limit of {1} approved attendance permissions for {2}.").format(
					self.employee, max_allowed, date.strftime("%B %Y")
				)
			)

