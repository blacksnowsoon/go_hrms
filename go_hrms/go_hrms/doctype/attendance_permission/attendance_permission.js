// Copyright (c) 2026, Gharieb Khalifa and contributors
// For license information, please see license.txt

frappe.ui.form.on("Attendance Permission", {
	// Triggered once when the form is created for the first time
	setup(frm) {
		setup_queries(frm)
	},
	// Triggered before the form is about to load
	async before_load(frm){
		await load_settings(frm)
	},
	// Triggered when the form is loaded and is about to render
	onload(frm) {
		set_permission_type_based_on_settings(frm);
		if (!frm.doc.posting_date) {
			frm.set_value("posting_date", frappe.datetime.get_today());
		}
		if (frm.doc.docstatus == 0) {
			return frappe.call({
				method: "hrms.hr.doctype.leave_application.leave_application.get_mandatory_approval",
				args: {
					doctype: "Leave Application",
				},
				callback: function (r) {
					if (!r.exc && r.message) {
						frm.toggle_reqd("leave_approver", true);
					}
				},
			});
		
		}
		
	},
	// Triggered when the form is loaded and rendered.
	refresh(frm) {
		frm.set_intro("");
		if (frm.doc.__islocal && !in_list(frappe.user_roles, "Employee")) {
			frm.set_intro(__("Fill the form and save it"));
		} else if (
			frm.perm[0] &&
			frm.perm[0].submit &&
			!frm.is_dirty() &&
			!frm.is_new() &&
			!frappe.model.has_workflow(frm.doctype) &&
			frm.doc.docstatus === 0
		) {
			frm.set_intro(__("Submit this Attendance Permission to confirm."));
		}
		if (frm.doc.employee) {
			frm.trigger("make_dashboard");
		}
	},
	// Triggered after the form is loaded and rendered
	onload_post_render(frm){
	},
	make_dashboard(frm) {
		let permission_details;

		if (frm.doc.employee) {
			frappe.call({
				method: "go_hrms.go_hrms.doctype.attendance_permission.attendance_permission_dashboard.get_permission_summary",
				async: false,
				args: {
					employee: frm.doc.employee,
				},
				callback: function (r) {
					if (!r.exc) {
						permission_details = r.message;
					}
				},
			});
			
			$("div").remove(".form-dashboard-section.custom");

			frm.dashboard.add_section(
				frappe.render_template("attendance_permission_dashboard", {
					data: permission_details,
				}),
				__("Permission Summary"),
			);
			frm.dashboard.show();
			frm.permission_details = permission_details;
		} else {
			$("div").remove(".form-dashboard-section.custom");
			frm.trigger("reset_permission_fields")
		}
	},
	async set_employee(frm) {
		if (frm.doc.employee) return;

		const employee = await hrms.get_current_employee(frm);
		if (employee) {
			frm.set_value("employee", employee);
		}
	},
	employee(frm) {
		if (frm.doc.permission_date) {
			frm.trigger("reset_permission_fields")
		}
		frm.trigger("make_dashboard");
	},
	after_save(frm) {
		
	},
	on_submit(frm) {
		
	},
	after_cancel(frm) {
		
	},
	permission_type(frm) {
		if (!frm.doc.shift_start_time || !frm.doc.shift_end_time) return;
		frm.trigger("adjust_permission_time");
	},
	async permission_date(frm) {
		frm.employee_leaves = [];
		await frm.trigger("get_emoployee_leaves");
		await frm.trigger("get_employee_shifts");
		frm.trigger("adjust_permission_time");
	},
	shift_assignment(frm) {
	},
	shift_start_time(frm) {
	},
	shift_end_time(frm) {
		if(!frm.doc.shift_end_time || !frm.doc.shift_start_time) return;
		frm.trigger("adjust_permission_time");
	},
	validate(frm) {
		
	},
	async get_employee_shifts(frm, set_defaults = true) {
		if (!frm.doc.permission_date || !frm.doc.employee) return;
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

				if (set_defaults) {
					const shift = r[0];
					frm.set_value("shift_type", shift.shift_type);
					frm.set_value("shift_assignment", shift.name);
				}
				frm.set_df_property("shift_assignment", "read_only", 0);

			} else {
				frm.employee_shifts = [];
				if (set_defaults) {
					err_message_dict('no_active_shifts')
					frm.trigger('reset_permission_fields')
				}
			}
		}); 
	},
	async get_emoployee_leaves(frm) {
		if (!frm.doc.employee || !frm.doc.permission_date) return;
		await frappe.db.get_list("Leave Application", {
			filters: {
				employee: frm.doc.employee,
				from_date: ["<=", frm.doc.permission_date],
				docstatus: 1,
				status: "Approved"
			},
			or_filters: [
				["to_date", ">=", frm.doc.permission_date],
				["to_date", "is", "not set"]
			],
			fields: ["name", "leave_type", "half_day", "custom_shift_part"]
		}).then((r) => {
			if (r && r.length >= 1) {
				frm.employee_leaves = r;
			}
		});
	},
	adjust_permission_time(frm) {
		const is_valid_permission = validate_permission(frm)
		
		if (is_valid_permission) {
			let minutes = frm.permission_settings.max_minutes_per_permission;
			if (frm.employee_leaves.length > 0) {
				const leave = frm.employee_leaves[0]
				if (leave.half_day && leave.custom_shift_part && frm.doc.shift_start_time && frm.doc.shift_end_time) {
					let [sh, sm, ss] = frm.doc.shift_start_time.split(":").map(Number);
					let [eh, em, es] = frm.doc.shift_end_time.split(":").map(Number);
					const total_start_shift_minuts = sh * 60 + sm
					const total_end_shift_miunts = eh * 60 + em
					minutes = (total_end_shift_miunts - total_start_shift_minuts) / 2 + minutes;
				}
			}
			
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
		
	},
	reset_permission_fields(frm) {
		frm.set_value({
			permission_type: null,
			permission_date: null,

			shift_assignment: null,
			shift_type: null,

			shift_start_time: null,
			shift_end_time: null,

			permitted_check_in_until: null,
			permitted_check_out_from: null
		});
	},
	

});

// Setup filters on link fields
function setup_queries(frm) {
	frm.set_query("approver", function () {
		return {
			query: "hrms.hr.doctype.department_approver.department_approver.get_approvers",
			filters: {
				employee: frm.doc.employee,
				doctype: "Leave Application"
			}
		}
	})

	frm.set_query("employee", erpnext.queries.employee);

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

// set permission type based on global settings
function set_permission_type_based_on_settings(frm) {
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

// validate the permission date 
function validate_permission(frm) {
	if (!frm.permission_settings
		|| !frm.permission_settings.max_minutes_per_permission
		|| !frm.doc.permission_date
		|| !frm.doc.employee
		|| !frm.doc.permission_type
	) return false
	if (frm.employee_leaves.length > 0) {
		const leave = frm.employee_leaves[0];
		if (leave && !leave.half_day) {
			err_message_dict("full_day_leave")
			return false
		}
	}
	const permission_date = frm.doc.permission_date
	const [y, m, d] = permission_date.split("-").map(Number)
	const abbr = get_abbr_month(m) + "-" + y % 100

	const approved_permissions = frm.permission_details[abbr]["Approved"]
	const open_permissions = frm.permission_details[abbr]["Open"]

	if (approved_permissions == 2) {
		err_message_dict("exceeded_limit")
		return false
	}
	if (open_permissions >= 1) {
		const match_date = frm.permission_details[abbr]["drafts"].filter((draft) => draft.day == d && draft.type == frm.doc.permission_type)
		if (match_date.length > 0) {
			err_message_dict("duplicate_permission_found")
			return false
		}
	}
	if (open_permissions == 2) {
		err_message_dict("max_draft_application")
		return false
	}

	return true
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


// ---------------------------------------------

function get_abbr_month(month) {
	ABBRS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
		"JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
	return ABBRS[month - 1]
}

function err_message_dict(state){
	frappe.msgprint(err_message_states[state])
}

const err_message_states = {
	full_day_leave: {
		title: __("Full Day Leave"),
		indicator: "red",
		message: __("Employee has already a full day leave on this date.")
	},
	exceeded_limit: {
		title: __("Limit Exceeded"),
		indicator: "red",
		message: __("Employee has already reached the maximum limit of approved attendance permissions for this month.")
	},
	already_existing_permission: {
		title: __("Already Existing Permission"),
		indicator: "red",
		message: __("Employee has already an attendance permission on this date.")
	},
	no_employee: {
		title: __("No Employee Found"),
		indicator: "red",
		message: __("Must Select An Employee")

	},
	no_active_shifts: {
		title: __("No Active Shifts"),
		indicatore: "red",
		message: __("No active shifts found fro the selected employee ")
	},
	duplicate_permission_found: {
		title: __("Duplicate Permission"),
		indicator: "red",
		message: __("Attendance Permission found with the same date")
	},
	max_draft_application: {
		title: __("Max Draft Application"),
		indicator: "red",
		message: __("There are 2 attendance permission in Draft mode!")
	}
}
// ---------------------------------

frappe.tour["Attendance Permission"] = [
	{
		fieldname: "employee",
		title: "Employee",
		description: __("Select the Employee."),
	},
	{
		fieldname: "permission_type",
		title: "Permission Type",
		description: __(
			"Select type of permission the employee wants to apply for, like Late Entry, Early Exit, etc.",
		),
	},
	{
		fieldname: "permission_date",
		title: "Permission Date",
		description: __("Select the date for your Attendance Permission."),
	},
	{
		fieldname: "approver",
		title: "Approver",
		description: __(
			"Select your Attendance Approver i.e. the person who approves or rejects your attendance permissions.",
		),
	},
];