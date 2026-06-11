
import frappe




def get_leave_multiplier(self):
    employee = frappe.get_cached_doc("Employee", self.employee)
    leave_type = frappe.get_cached_doc("Leave Type", self.leave_type)

    if (
        employee.custom_is_rotational_shift_employee
        and leave_type.custom_apply_rotational_multiplier
    ):
        return 2

    return 1