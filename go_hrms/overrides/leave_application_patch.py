import frappe

from hrms.hr.doctype.leave_application.leave_application import LeaveApplication

from go_hrms.utils.helper import get_leave_multiplier


_original_method = LeaveApplication.create_leave_ledger_entry


def custom_create_leave_ledger_entry(self, submit=True):

    multiplier = get_leave_multiplier(self)

    original_days = self.total_leave_days

    self.total_leave_days = original_days * multiplier

    try:
        return _original_method(
            self,
            submit
        )
    finally:
        self.total_leave_days = original_days


LeaveApplication.create_leave_ledger_entry = custom_create_leave_ledger_entry