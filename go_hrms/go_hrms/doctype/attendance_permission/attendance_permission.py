# Copyright (c) 2026, Gharieb Khalifa and contributors
# For license information, please see license.txt

from datetime import datetime, timedelta
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import (getdate, get_time, get_datetime, cint)
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
	
	def before_save(self):
		if self.permission_type == "Late Entry":
			self.permitted_check_out_from = None
		elif self.permission_type == "Early Exit":
			self.permitted_check_in_until = None

	def after_insert(self):
		if frappe.db.get_single_value("Attendance Permission Settings", "send_permission_notification"):
			self.notify_permission_approver()
	
	def validate(self):
		validate_active_employee(self.employee)
		set_employee_name(self)
		self.validate_max_permissions_per_month()
		self.validate_permission_overlap()

	def on_update(self):
		if self.status == "Open" and self.docstatus < 1:
			# notify approver about creation
			if frappe.db.get_single_value("Attendance Permission Settings", "send_permission_notification"):
				self.notify_permission_approver()

			# share doc
			# share_doc_with_approver(self, self.approver)
	
	def on_submit(self):
		if self.status in ["Open", "Cancelled"]:
			frappe.throw(_("Only Permissions with status 'Approved' and 'Rejected' can be submitted"))
		self.update_attendance()
		self.reload()
		
		#notify permission applier about approval
		if frappe.db.get_single_value("Attendance Permission Settings", "send_permission_notification"):
			self.notify_employee()
	
	def before_cancel(self):
		self.status = "Cancelled"
		if self.attendance_marked:
			attendance = frappe.get_doc("Attendance", self.attendance_marked)
			self.permitted_check_in_until = None
			self.permitted_check_out_from = None
			updated_attendance = add_remove_attendance_logic(attendance, self)
			updated_attendance.flags.ignore_validate_update_after_submit = True
			updated_attendance.flags.ignore_permission = True
			updated_attendance.save()

		# notify permission aplier about cancelation
		if frappe.db.get_single_value("Attendance Permission Settings", "send_permission_notification"):
			self.notify_employee()
	
	def update_attendance(self):
		if self.status != "Approved":
			return

		attendance_name = frappe.db.get_value("Attendance", filters={
			"employee": self.employee,
			"attendance_date": self.permission_date,
			"status": "Present"
		}, fieldname="name")
		
		if attendance_name:
			attendance = frappe.get_doc("Attendance", attendance_name)
			permitted_time = self.permitted_check_in_until if self.permission_type == "Late Entry" else self.permitted_check_out_from
			if permitted_time:
				updated_attendance = add_remove_attendance_logic(attendance, self)
				updated_attendance.flags.ignore_validate_update_after_submit = True
				updated_attendance.flags.ignore_permission = True
				updated_attendance.save()
				self.attendance_marked = attendance_name
				self.db_set("attendance_marked", attendance_name)
	
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
		
		next_month = start_date.replace(day=28) + timedelta(days=4)
		end_date = next_month.replace(day=1) - timedelta(days=1)

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
	


@frappe.whitelist()
def add_remove_attendance_logic(attendance, att_permission):
	late_entry = "Late Entry"
	early_exit = "Early Exit"
	permission_type = att_permission.permission_type

	if not permission_type:
		return attendance
	if permission_type not in [late_entry , early_exit]:
		return attendance

	permitted_time = (
		att_permission.get("permitted_check_in_until") 
		if permission_type == late_entry 
		else att_permission.get("permitted_check_out_from")
	)

	if permission_type == late_entry:
		handle_late_entry_permission(attendance, permitted_time)
	
	elif permission_type == early_exit:
		handle_early_exit_permission(attendance, permitted_time)
	return attendance

# --- Permission Handlers ---

def handle_late_entry_permission(attendance, permitted_time):
	"""Handles logic variation when adding or removing Late Entry permissions."""
	if permitted_time:
		attendance.custom_allowed_in_time_until = permitted_time
		if get_time(attendance.in_time) <= get_time(permitted_time):
			attendance.late_entry = 0
	else:
		attendance.custom_allowed_in_time_until = None
		attendance.late_entry = 1 if calculate_fallback_late_entry(attendance) else 0


def handle_early_exit_permission(attendance, permitted_time):
	"""Handles logic variation when adding or removing Early Exit permissions."""
	if permitted_time:
		attendance.custom_allowed_out_time_from = permitted_time
		if get_time(attendance.out_time) >= get_time(permitted_time):
			attendance.early_exit = 0
	else:
		attendance.custom_allowed_out_time_from = None
		attendance.early_exit = 1 if calculate_fallback_early_exit(attendance) else 0


# --- Core Shift Math Engine ---

def calculate_fallback_late_entry(attendance) -> bool:
	"""Calculates if an attendance record should be marked late based on its shift."""
	if not (attendance.shift and attendance.in_time):
		return False

	shift = frappe.get_doc("Shift Type", attendance.shift)
	if not cint(shift.enable_late_entry_marking):
		return False

	shift_start = datetime.combine(getdate(attendance.attendance_date), get_time(shift.start_time))
	late_limit = shift_start + timedelta(minutes=cint(shift.late_entry_grace_period))

	return get_datetime(attendance.in_time) > late_limit


def calculate_fallback_early_exit(attendance) -> bool:
	"""Calculates if an attendance record should be marked as an early exit based on its shift."""
	if not (attendance.shift and attendance.out_time):
		return False

	shift = frappe.get_doc("Shift Type", attendance.shift)
	if not cint(shift.enable_early_exit_marking):
		return False

	start_time = get_time(shift.start_time)
	end_time = get_time(shift.end_time)

	# Check for overnight cross-day shifts smoothly
	days_to_add = 1 if start_time >= end_time else 0
	shift_end = datetime.combine(getdate(attendance.attendance_date) + timedelta(days=days_to_add), end_time)

	early_limit = shift_end - timedelta(minutes=cint(shift.early_exit_grace_period))

	return get_datetime(attendance.out_time) < early_limit