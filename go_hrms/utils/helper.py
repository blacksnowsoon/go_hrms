
import frappe




def get_leave_multiplier_by_values(employee, leave_type):
    employee = frappe.get_cached_doc("Employee", employee)
    leave_type = frappe.get_cached_doc("Leave Type", leave_type)

    if (
        employee.custom_is_rotational_shift_employee
        and leave_type.custom_apply_rotational_multiplier
    ):
        return 2

    return 1


def get_leave_multiplier(doc):
    return get_leave_multiplier_by_values(
        doc.employee,
        doc.leave_type
    )