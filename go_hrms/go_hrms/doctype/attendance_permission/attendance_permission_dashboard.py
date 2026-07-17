import frappe
from frappe import _
from frappe.utils import getdate, today


def get_data():
	return {}


@frappe.whitelist()
def get_permission_summary(employee: str) -> dict:
	"""
	Returns a dict keyed by short month labels (e.g. "JAN-26") spanning from
	the start month of the configured Leave Period up to the current month.
	Each value contains the monthly allocation limit plus a count per status:

	{
	    "JAN-26": {"allocated": 3, "Open": 1, "Approved": 2, "Rejected": 0, "Cancelled": 0, "balance": 1},
	    "FEB-26": {"allocated": 3, "Open": 0, "Approved": 0, "Rejected": 0, "Cancelled": 0, "balance": 3},
	    ...
	}
	"""
	if not employee:
		frappe.throw(_("Employee is required"))

	STATUSES = ["Open", "Approved", "Rejected", "Cancelled"]

	# ── 1. Fetch settings: allocation limit + linked leave period ────────────
	settings = frappe.db.get_singles_dict("Attendance Permission Settings")
	allocated = int(settings.get("max_permisson_per_month") or 0)
	leave_period_name = settings.get("linked_leave_period")

	if not leave_period_name:
		frappe.throw(_("No Linked Leave Period configured in Attendance Permission Settings."))

	# ── 2. Get the leave period's start date ────────────────────────────────
	is_active_leave_period = frappe.db.get_value("Leave Period", leave_period_name, "is_active")
	if is_active_leave_period == 0:
		frappe.throw(_("Leave Period {0} is not active.").format(leave_period_name))

	period_from_date = frappe.db.get_value("Leave Period", leave_period_name, "from_date")
	if not period_from_date:
		frappe.throw(_("Leave Period {0} has no start date.").format(leave_period_name))

	period_start = getdate(period_from_date)
	current_date = getdate(today())

	# ── 3. Build month keys from period start → current month ────────────────
	#       Label format: "JAN-26", "FEB-26", etc.
	months: list[str] = []
	year, month = period_start.year, period_start.month
	while (year, month) <= (current_date.year, current_date.month):
		label = f"{_get_month_abbr(month)}-{str(year)[-2:]}"
		months.append(label)
		if month == 12:
			year, month = year + 1, 1
		else:
			month += 1

	# ── 4. Initialise every month slot with zero counts ──────────────────────
	summary: dict = {
		m: {"allocated": allocated, **{s: 0 for s in STATUSES},"drafts": []}
		for m in months
	}

	# ── 5. Fetch employee permissions within the leave period ────────────────
	records = frappe.get_all(
		"Attendance Permission",
		filters={
			"employee": employee,
			"docstatus": ["!=", 2],  # exclude amended/trashed
			"permission_date": [">=", period_from_date],
		},
		fields=["permission_date", "status", "permission_type"],
		order_by="permission_date asc",
	)

	# ── 6. Tally records into their month buckets ────────────────────────────
	for rec in records:
		d = getdate(rec.permission_date)
		pt = rec.permission_type
		# Only count up to the current month
		if (d.year, d.month) > (current_date.year, current_date.month):
			continue
		label = f"{_get_month_abbr(d.month)}-{str(d.year)[-2:]}"
		status = rec.status or "Open"
		if label in summary and status in STATUSES:
			summary[label][status] += 1 
			if status == "Open" :
				summary[label]["drafts"].append({"day": d.day, "type":pt}) 

	# ── 7. Compute balance = allocated − Approved (floor at 0) ───────────────
	for month_data in summary.values():
		month_data["balance"] = max(0, allocated - month_data["Approved"])

	return summary


def _get_month_abbr(month: int) -> str:
	"""Return uppercase 3-letter month abbreviation for a month number (1-12)."""
	ABBRS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
	         "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
	return ABBRS[month - 1]