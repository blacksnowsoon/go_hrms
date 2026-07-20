
from hrms.hr.doctype.shift_type import shift_type
from hrms.hr.doctype.shift_type.shift_type import (
    skip_attendance_in_checkins,
    get_existing_half_day_attendance,
    update_attendance_in_checkins,
    handle_attendance_exception,
)

from go_hrms.go_hrms.doctype.attendance_permission.attendance_permission 
import add_remove_attendance_logic

_original_mark_attendance_and_link_log = shift_type.mark_attendance_and_link_log


def custom_mark_attendance_and_link_log(logs,
	attendance_status,
	attendance_date,
	working_hours=None,
	late_entry=False,
	early_exit=False,
	in_time=None,
	out_time=None,
	shift=None,):
    """Creates an attendance and links the attendance to the Employee Checkin.
	Note: If attendance is already present for the given date, the logs are marked as skipped and no exception is thrown.

	:param logs: The List of 'Employee Checkin'.
	:param attendance_status: Attendance status to be marked. One of: (Present, Absent, Half Day, Skip). Note: 'On Leave' is not supported by this function.
	:param attendance_date: Date of the attendance to be created.
	:param working_hours: (optional)Number of working hours for the given date.
	"""
	log_names = [x.name for x in logs]
	employee = logs[0].employee

	if attendance_status == "Skip":
		skip_attendance_in_checkins(log_names)
		return None

	elif attendance_status in ("Present", "Absent", "Half Day"):
		try:
			frappe.db.savepoint("attendance_creation")
			if attendance := get_existing_half_day_attendance(employee, attendance_date):
				frappe.db.set_value(
					"Attendance",
					attendance.name,
					{
						"working_hours": working_hours,
						"shift": shift,
						"late_entry": late_entry,
						"early_exit": early_exit,
						"in_time": in_time,
						"out_time": out_time,
						"half_day_status": "Absent" if attendance_status == "Absent" else "Present",
						"modify_half_day_status": 0,
					},
				)
                # check the attendance permission on the attendance date
                attendance_permission_name = frappe.db.is_exist("Attendance Permission", {
                    "employee": employee,
                    "permission_date": attendance_date,
                    "status": "Approved"
                })
                if attendance_permission_name:
                    attendance_permission = frappe.getdoc("Attendance Permission", attendance_permission_name)
                    attendance = add_remove_attendance_logic(attendance, attendance_permission)

			else:
				attendance = frappe.new_doc("Attendance")
				attendance.update(
					{
						"doctype": "Attendance",
						"employee": employee,
						"attendance_date": attendance_date,
						"status": attendance_status,
						"working_hours": working_hours,
						"shift": shift,
						"late_entry": late_entry,
						"early_exit": early_exit,
						"in_time": in_time,
						"out_time": out_time,
						"half_day_status": "Absent" if attendance_status == "Half Day" else None,
					}
				)
				attendance = add_remove_attendance_logic(attendance, attendance_permission)
				attendance.submit()

			if attendance_status == "Absent":
				attendance.add_comment(
					text=_("Employee was marked Absent for not meeting the working hours threshold.")
				)

			update_attendance_in_checkins(log_names, attendance.name)
			return attendance

		except frappe.ValidationError as e:
			handle_attendance_exception(log_names, e)

	else:
		frappe.throw(_("{} is an invalid Attendance Status.").format(attendance_status))

# Patch 1: patch the mark_attendance_and_link_log to apply the attendance permission
shift_type.mark_attendance_and_link_log = custom_mark_attendance_and_link_log
	