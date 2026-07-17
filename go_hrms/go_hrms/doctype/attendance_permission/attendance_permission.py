# Copyright (c) 2026, Gharieb Khalifa and contributors
# For license information, please see license.txt

import datetime
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate
from hrms.hr.utils import (
	get_holiday_dates_for_employee,
	get_leave_period,
	set_employee_name,
	share_doc_with_approver,
	validate_active_employee,
)
from hrms.mixins.pwa_notifications import PWANotificationsMixin
from hrms.utils import get_employee_email

class AttendancePermission(Document, PWANotificationsMixin):
	def get_feed(self):
		return _("{0}: From {0} of type {1}").format(self.employee_name, self.permission_type)
	
	def after_save(self):
		self.notify_approver()
	
	def validate(self):
		validate_active_employee(self.employee)
		set_employee_name(self)
		self.validate_max_permissions_per_month()
		self.validate_permission_overlap()

	def on_update(self):
		pass
	
	def on_submit(self):
		if self.status in ["Open", "Cancelled"]:
			frappe.throw(_("Only Permissions with status 'Approved' and 'Rejected' can be submitted"))
		#notify permission applier about approval
		if frappe.db.get_single_value("Attendance Permission", "send_permission_notification")
			self.notify_employee()
	
	def before_cancel(self):
		self.status = "Cancelled"

		# notify permission aplier about cancelation
		if frappe.db.get_single_value("Attendance Permission", "send_permission_notification")
			self.notify_employee()
	
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
		
	def validate_permission_overlap(self):
		exist_permission = frappe.db.get_all("Attendance Permission", filters={
			"employee": self.employee,
			"workflow_state": ["in", ["Approved", "Open"]],
			"permission_type": self.permission_type,
			"permission_date": self.permission_date,
			"name": ["!=", self.name],
			},
			fields=["name"]
		)
		if len(exist_permission) > 0 :
			frappe.throw(
				_("Same Attendance Permission Exist for this day")
			)

	def notify_employee(self):
		employee_email = get_employee_email(self.employee)

		if not employee_email:
			return

		parent_doc = frappe.get_doc("Attendance Permission", self.name)
		args = parent_doc.as_dict()

		template = frappe.db.get_single_value("Attendance Permission Settings", "status_notification_template")
		if not template:
			frappe.msgprint(_("Please set default template for Attendance Permission Status Notification in Attendance Permission Settings."))
			return
		email_template = frappe.get_doc("Email Template", template)
		subject = frappe.render_template(email_template.subject, args)
		message = frappe.render_template(email_template.response_, args)

		self.notify(
			{
				# for post in messages
				"message": message,
				"message_to": employee_email,
				# for email
				"subject": subject,
				"notify": "employee",
			}
		)

	def notify_permission_approver(self):
		if self.approver:
			parent_doc = frappe.get_doc("Attendance Permission", self.name)
			args = parent_doc.as_dict()

			template = frappe.db.get_single_value("Attendance Permission Settings", "approval_notification_template")
			if not template:
				frappe.msgprint(
					_("Please set default template for Attendance Permission Approval Notification in Attendance Permission Settings.")
				)
				return
			email_template = frappe.get_doc("Email Template", template)
			subject = frappe.render_template(email_template.subject, args)
			message = frappe.render_template(email_template.response_, args)

			self.notify(
				{
					# for post in messages
					"message": message,
					"message_to": self.leave_approver,
					# for email
					"subject": subject,
				}
			)

	def notify(self, args):
		args = frappe._dict(args)
		# args -> message, message_to, subject
		if cint(self.follow_via_email):
			contact = args.message_to
			if not isinstance(contact, list):
				if not args.notify == "employee":
					contact = frappe.get_doc("User", contact).email or contact

			sender = dict()
			sender["email"] = frappe.get_doc("User", frappe.session.user).email
			sender["full_name"] = get_fullname(sender["email"])

			try:
				frappe.sendmail(
					recipients=contact,
					sender=sender["email"],
					subject=args.subject,
					message=args.message,
				)
				frappe.msgprint(_("Email sent to {0}").format(contact))
			except frappe.OutgoingEmailError:
				pass