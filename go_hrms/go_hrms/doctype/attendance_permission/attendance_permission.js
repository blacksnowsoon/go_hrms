// Copyright (c) 2026, Gharieb Khalifa and contributors
// For license information, please see license.txt

frappe.ui.form.on("Attendance Permission", {
	async onload(frm) {
		if (frm.is_new() || frm.doc.docstatus === 0) {
			await load_settings(frm);
		}
		if (frm.is_new()) {
			await setup_current_user(frm);
			configure_permission_type(frm);
		}
		setup_queries(frm);
	},

	async refresh(frm) {
		if (frm.doc.docstatus === 0) {
			if (frm.doc.employee && frm.doc.permission_date && (!frm.employee_shifts || !frm.employee_shifts.length)) {
				await fetch_employee_shift(frm);
			}
			setup_queries(frm);
		}
	},

	employee(frm) {
		frm.employee_shifts = [];
		frm.set_value("permission_date", null);
	},

	permission_type(frm) {
		if (frm.doc.permission_date) {
			adjust_shift_time(frm);
		}
	},

	async permission_date(frm) {
		const employee = frm.doc.employee;
		const permission_date = frm.doc.permission_date;

		if (permission_date && !employee) {
			frappe.msgprint(__("Please select an employee first"));
			frm.set_value("permission_date", null);
		} else if (employee && permission_date) {
			await fetch_employee_shift(frm);
		} else {
			reset_form(frm);
		}
	},

	shift_assignment(frm) {
		if (frm.doc.shift_assignment && (frm.employee_shifts || []).length) {
			const selected_shift = frm.employee_shifts.find(s => s.name === frm.doc.shift_assignment);
			if (selected_shift) {
				frm.set_value("shift_type", selected_shift.shift_type);
			}
			frm.set_df_property("shift_type", "read_only", 0);
		} else {
			frm.set_value("shift_type", null);
			frm.set_df_property("shift_type", "read_only", 1);
		}
	},

	shift_start_time(frm) {
		adjust_shift_time(frm);
	},

	shift_end_time(frm) {
		adjust_shift_time(frm);
	}
});

// Setup filters on link fields based on fetched shifts
function setup_queries(frm) {
	frm.set_query("shift_assignment", () => {
		const shift_names = (frm.employee_shifts || []).map(s => s.name);
		return {
			filters: {
				name: ["in", shift_names.length ? shift_names : [""]]
			}
		};
	});

	frm.set_query("shift_type", () => {
		const shift_types = (frm.employee_shifts || []).map(s => s.shift_type);
		return {
			filters: {
				name: ["in", shift_types.length ? shift_types : [""]]
			}
		};
	});
}

// load the global settings of Attendance Permission
async function load_settings(frm) {
	await frappe.call({
		method: "frappe.client.get",
		args: {
			doctype: "Attendance Permission Settings"
		},
		callback: function(r){
			if (r.message) { 
				frm.permission_settings = { ...r.message }
			}
		}
	})
}

// setup current user if he is employee self service
async function setup_current_user(frm) {
	if (
		!frappe.user.has_role("Employee Self Service")
		|| frappe.user.has_role("HR Manager")
		|| frappe.user.has_role("HR User")
		|| frappe.user.has_role("System Manager")
	) return

	const employee = await frappe.db.get_value("Employee",
		{
			user_id : frappe.session.user
		},
		"name"
	)
	
	if (employee.message) {
		await frm.set_value("employee", employee.message.name)
		frm.set_df_property("employee", "read_only", 1)
	}
}

// configure permission type based on global settings
function configure_permission_type(frm) {
	const settings = frm.permission_settings
	if (!settings) return;

	if (settings.allow_late_entry && !settings.allow_early_exit) {
		frm.set_value(
			"permission_type",
			"Late Entry"
		);
		frm.set_df_property("permission_type", "read_only", 1)
	}
	if (settings.allow_early_exit && !settings.allow_late_entry) {
		frm.set_value(
			"permission_type",
			"Early Exit"
		);
		frm.set_df_property("permission_type", "read_only", 1)
	}

}

// fetch employee shift assignment based on permission date
async function fetch_employee_shift(frm) {
	await frappe.db.get_list("Shift Assignment", {
		filters: {
			employee: frm.doc.employee,
			start_date: ["<=", frm.doc.permission_date],
			docstatus: 1,
			status: "Active"
		},
		or_filters: [
			["end_date", ">=", frm.doc.permission_date],
			["end_date", "is", "not set"]
		],
		fields: ["name", "shift_type"]
	}).then((r) => {
		if (r && r.length) {
			frm.employee_shifts = r;
			setup_queries(frm);

			const shift = r[0];
			frm.set_value("shift_type", shift.shift_type);
			frm.set_value("shift_assignment", shift.name);
			frm.set_df_property("shift_assignment", "read_only", 0);
		} else {
			frm.employee_shifts = [];
			setup_queries(frm);
			frappe.msgprint(__("No active Shift Assignment found for this employee on the selected date."));
			reset_form(frm);
		}
	});
}

// adjust permitted check in/out time based on permission type and global settings
function adjust_shift_time(frm) {
	if (!frm.permission_settings) return;
	
	const minutes = frm.permission_settings.max_minutes_per_permission;
	if (!minutes) return;

	if (frm.doc.permission_type === "Late Entry" && frm.doc.shift_start_time) {
		const entry_time = frm.doc.shift_start_time;
		const target_time = add_minutes(entry_time, minutes);
		if (frm.doc.permitted_check_in_until !== target_time) {
			frm.set_value("permitted_check_in_until", target_time);
			frm.set_value("permitted_check_out_from", null);
		}
	}
	if (frm.doc.permission_type === "Early Exit" && frm.doc.shift_end_time) {
		const exit_time = frm.doc.shift_end_time;
		const target_time = add_minutes(exit_time, -minutes);
		if (frm.doc.permitted_check_out_from !== target_time) {
			frm.set_value("permitted_check_out_from", target_time);
			frm.set_value("permitted_check_in_until", null);
		}
	}
}

// add/subtract minutes from time string format HH:MM:SS
function add_minutes(time, minutes) {
	if (!time) return null;

	let [h, m, s] = time.split(":").map(Number);

	let total_minutes = h * 60 + m + minutes;


	total_minutes = ((total_minutes % 1440) + 1440) % 1440;

	h = Math.floor(total_minutes / 60);
	m = total_minutes % 60;

	return (
		String(h).padStart(2, "0") + ":" +
		String(m).padStart(2, "0") + ":" +
		String(s || 0).padStart(2, "0")
	);
}

// reset the form to its initial state when employee is changed or removed
function reset_form(frm) {
	frm.set_value({
		permission_type: null,

		shift_assignment: null,
		shift_type: null,

		shift_start_time: null,
		shift_end_time: null,

		permitted_check_in_until: null,
		permitted_check_out_from: null
	});
}