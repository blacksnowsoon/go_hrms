import frappe
import datetime
from frappe.utils import getdate
	

from hrms.hr.doctype.leave_application.leave_application import LeaveApplication
from go_hrms.utils.helper import get_leave_multiplier

from hrms.hr.doctype.leave_application import leave_application
from hrms.hr.report.employee_leave_balance import employee_leave_balance
from hrms.hr.doctype.leave_application.leave_application import get_leave_entries
# from hrms.hr.doctype.leave_application.leave_application import get_number_of_leave_days



_original_create_leave_ledger_entry = LeaveApplication.create_leave_ledger_entry

def custom_create_leave_ledger_entry(self, submit=True):

    multiplier = get_leave_multiplier(self)

    original_days = self.total_leave_days

    self.total_leave_days = original_days * multiplier

    try:
        return _original_create_leave_ledger_entry(
            self,
            submit
        )
    finally:
        self.total_leave_days = original_days

# Patch 1: Patch the create_leave_ledger_entry method to apply rotational shift multiplier
LeaveApplication.create_leave_ledger_entry = custom_create_leave_ledger_entry

#-----------------------------------------------------------------

_original_get_leaves_for_period = leave_application.get_leaves_for_period

def custom_get_leaves_for_period(
	employee: str,
	leave_type: str,
	from_date: datetime.date,
	to_date: datetime.date,
	skip_expired_leaves: bool = True,
) -> float:
	leave_entries = get_leave_entries(employee, leave_type, from_date, to_date)
	leave_days = 0

	
	for leave_entry in leave_entries:
		inclusive_period = leave_entry.from_date >= getdate(from_date) and leave_entry.to_date <= getdate(
			to_date
		)

		if inclusive_period and leave_entry.transaction_type == "Leave Encashment":
			leave_days += leave_entry.leaves

		elif (
			inclusive_period
			and leave_entry.transaction_type == "Leave Allocation"
			and leave_entry.is_expired
			and not skip_expired_leaves
		):
			leave_days += leave_entry.leaves

		elif leave_entry.transaction_type == "Leave Application":
			if leave_entry.from_date < getdate(from_date):
				leave_entry.from_date = from_date
			if leave_entry.to_date > getdate(to_date):
				leave_entry.to_date = to_date

			half_day = 0
			half_day_date = None
			# fetch half day date for leaves with half days
			if leave_entry.leaves % 1:
				half_day = 1
				half_day_date = frappe.db.get_value(
					"Leave Application", leave_entry.transaction_name, "half_day_date"
				)
			leave_days += leave_entry.leaves

	return leave_days


# Patch 2: Patch the get_leaves_for_period function to apply rotational shift multiplier
leave_application.get_leaves_for_period = custom_get_leaves_for_period
employee_leave_balance.get_leaves_for_period = custom_get_leaves_for_period
