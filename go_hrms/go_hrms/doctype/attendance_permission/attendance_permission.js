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
					console.log(r)
					if (!r.exc) {
						permission_details = r.message;
					}
				},
			});
			let allowed_permission_types = Object.keys(permission_details);
			console.log("alowed _permission_types", allowed_permission_types)
			$("div").remove(".form-dashboard-section.custom");

			frm.dashboard.add_section(
				frappe.render_template("attendance_permission_dashboard", {
					data: permission_details,
				}),
				__("Permission Summary"),
			);
			frm.dashboard.show();
			;
			
			// frm.set_query("permission_type", function () {
			// 	return {
			// 		filters: [["permission_type_name", "in", allowed_permission_types]],
			// 	};
			// });
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
		frm.set_value("permission_date", null);
		frm.trigger("make_dashboard");
	},
	after_save(frm) {
		
	},
	on_submit(frm) {
		
	},
	after_cancel(frm) {
		
	},

	permission_type(frm) {
		
	},

	permission_date(frm) {
		if (!frm.doc.employee) {
			
			frappe.msgprint(__("Please select an Employee first."));
			return;
		}
	},

	shift_assignment(frm) {
		
	},

	shift_start_time(frm) {
		
	},

	shift_end_time(frm) {
		
	},
	validate(frm) {
		
	}
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
async function fetch_employee_shift(frm, set_defaults = true) {
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

			if (set_defaults) {
				const shift = r[0];
				frm.set_value("shift_type", shift.shift_type);
				frm.set_value("shift_assignment", shift.name);
			}
			frm.set_df_property("shift_assignment", "read_only", 0);
		} else {
			frm.employee_shifts = [];
			setup_queries(frm);
			if (set_defaults) {
				frappe.msgprint(__("No active Shift Assignment found for this employee on the selected date."));
				reset_form(frm);
			}
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

// fetch and render statistics of employee attendance permissions
async function fetch_and_render_attendance_stats(frm) {
	if (!frm.doc.employee) {
		frm.dashboard.wrapper.find(".attendance-stats-section").remove();
		return;
	}

	if (!frm.permission_settings) {
		await load_settings(frm);
	}

	// let effective_from = frm.permission_settings && frm.permission_settings.effective_from;
	// if (!effective_from) {
		// Fallback to January of current year if effective_from is not set
		const current_year = new Date().getFullYear();
		let effective_from = `${current_year}-01-01`;
	// }

	const parts = effective_from.split("-");
	const start_date = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, 1);

	const today = new Date();
	const today_year_month = today.getFullYear() * 12 + today.getMonth();

	const months = [];
	let current = new Date(start_date);
	while (current.getFullYear() * 12 + current.getMonth() <= today_year_month) {
		months.push({
			year: current.getFullYear(),
			month: current.getMonth(),
			label: current.toLocaleDateString("default", { month: "short", year: "2-digit" }),
			year_month: `${current.getFullYear()}-${String(current.getMonth() + 1).padStart(2, "0")}`
		});
		current.setMonth(current.getMonth() + 1);
	}

	const first_month_start = new Date(start_date.getFullYear(), start_date.getMonth(), 1);
	const last_month_end = new Date(today.getFullYear(), today.getMonth() + 1, 0);

	const start_date_str = format_date_to_yyyy_mm_dd(first_month_start);
	const end_date_str = format_date_to_yyyy_mm_dd(last_month_end);

	const permissions = await frappe.db.get_list("Attendance Permission", {
		filters: {
			employee: frm.doc.employee,
			workflow_state: ["in", ["Draft", "Pending", "Approved", "Cancelled"]],
			permission_date: ["between", [start_date_str, end_date_str]]
		},
		fields: ["name", "workflow_state", "permission_date"],
		limit: 1000
	});

	const counts = {};
	const statuses = ["Draft", "Pending", "Approved", "Cancelled"];
	statuses.forEach(status => {
		counts[status] = {};
		months.forEach(m => {
			counts[status][m.year_month] = 0;
		});
	});

	if (permissions && permissions.length) {
		permissions.forEach(p => {
			if (p.permission_date) {
				const state = p.workflow_state || "Draft";
				const date_parts = p.permission_date.split("-");
				const p_year_month = `${date_parts[0]}-${date_parts[1]}`;
				if (counts[state] && counts[state][p_year_month] !== undefined) {
					counts[state][p_year_month]++;
				}
			}
		});
	}

	// Build a beautifully designed HTML table card
	let html_content = `
		<style>
			.attendance-stats-card {
				background: var(--card-bg, var(--fg-color, #fff));
				border-radius: 12px;
				box-shadow: var(--shadow-sm, 0 1px 3px rgba(0,0,0,0.12));
				border: 1px solid var(--border-color, #e2e8f0);
				margin-bottom: 20px;
				overflow: hidden;
				transition: box-shadow 0.3s ease;
			}
			.attendance-stats-card:hover {
				box-shadow: var(--shadow-md, 0 4px 6px rgba(0,0,0,0.15));
			}
			.attendance-stats-header {
				background: linear-gradient(135deg, #4f46e5 0%, #3b82f6 100%);
				padding: 12px 16px;
				display: flex;
				align-items: center;
				color: #ffffff;
			}
			.attendance-stats-header h5 {
				margin: 0;
				font-size: 14px;
				font-weight: 600;
				color: #fff !important;
				letter-spacing: 0.5px;
			}
			.attendance-stats-table-wrapper {
				overflow-x: auto;
			}
			.attendance-stats-table {
				width: 100%;
				border-collapse: collapse;
				font-size: 12px;
			}
			.attendance-stats-table th {
				background-color: var(--bg-color, #f8fafc);
				color: var(--text-muted, #64748b);
				font-weight: 600;
				padding: 10px 14px;
				text-align: center;
				border-bottom: 2px solid var(--border-color, #e2e8f0);
				white-space: nowrap;
			}
			.attendance-stats-table th:first-child {
				text-align: left;
				padding-left: 18px;
			}
			.attendance-stats-table td {
				padding: 10px 14px;
				text-align: center;
				border-bottom: 1px solid var(--border-color, #f1f5f9);
				color: var(--text-color, #334155);
			}
			.attendance-stats-table td:first-child {
				text-align: left;
				padding-left: 18px;
				font-weight: 600;
			}
			.attendance-stats-table tr:last-child td {
				border-bottom: none;
			}
			.attendance-stats-table tr:hover td {
				background-color: var(--bg-color, #f8fafc);
			}
			.badge-count {
				display: inline-block;
				min-width: 20px;
				padding: 2px 6px;
				border-radius: 10px;
				font-size: 11px;
				font-weight: 600;
				text-align: center;
			}
			.badge-count.has-count {
				background-color: #eff6ff;
				color: #2563eb;
			}
			.badge-count.zero-count {
				color: #94a3b8;
			}
			.status-row-Draft { color: #64748b !important; }
			.status-row-Pending { color: #d97706 !important; }
			.status-row-Approved { color: #059669 !important; }
			.status-row-Cancelled { color: #dc2626 !important; }
		</style>
		<div class="attendance-stats-card">
			<div class="attendance-stats-header">
				<h5>Attendance Permission Statistics</h5>
			</div>
			<div class="attendance-stats-table-wrapper">
				<table class="attendance-stats-table">
					<thead>
						<tr>
							<th style="min-width: 120px;">Status</th>
							${months.map(m => `<th>${m.label}</th>`).join("")}
						</tr>
					</thead>
					<tbody>
						${statuses.map(status => `
							<tr>
								<td class="status-row-${status}">${status}</td>
								${months.map(m => {
									const val = counts[status][m.year_month] || 0;
									const badge_class = val > 0 ? "has-count" : "zero-count";
									return `<td><span class="badge-count ${badge_class}">${val}</span></td>`;
								}).join("")}
							</tr>
						`).join("")}
					</tbody>
				</table>
			</div>
		</div>
	`;

	let $section = frm.dashboard.stats_area.wrapper.find(".section-body")
	console.log($section)
	if (!$section.length) {
		$section = $('<div class="attendance-stats-section" style="padding: 15px 0;"></div>').appendTo(frm.dashboard.wrapper);
		console.log($section)
	}
	$section.html(html_content);
	frm.dashboard.stats_area.show();
}

function format_date_to_yyyy_mm_dd(date) {
	const yyyy = date.getFullYear();
	const mm = String(date.getMonth() + 1).padStart(2, "0");
	const dd = String(date.getDate()).padStart(2, "0");
	return `${yyyy}-${mm}-${dd}`;
}

async function check_max_permissions_limit(frm) {
	if (!frm.doc.employee || !frm.doc.permission_date) return;

	if (!frm.permission_settings) {
		await load_settings(frm);
	}

	const max_allowed = frm.permission_settings ? frm.permission_settings.max_permisson_per_month : null;
	if (max_allowed === null || max_allowed === undefined) return;

	const date = frm.doc.permission_date;
	const parts = date.split("-");
	const year = parseInt(parts[0]);
	const month = parseInt(parts[1]);
	
	const start_of_month = `${parts[0]}-${parts[1]}-01`;
	const last_day = new Date(year, month, 0).getDate();
	const end_of_month = `${parts[0]}-${parts[1]}-${String(last_day).padStart(2, "0")}`;

	const permissions = await frappe.db.get_list("Attendance Permission", {
		filters: {
			employee: frm.doc.employee,
			workflow_state: "Approved",
			permission_date: ["between", [start_of_month, end_of_month]],
			name: ["!=", frm.doc.name]
		},
		fields: ["name"]
	});

	const approved_count = permissions ? permissions.length : 0;
	if (approved_count >= max_allowed) {
		frappe.msgprint({
			title: __("Limit Exceeded"),
			indicator: "red",
			message: __("Employee has already reached the maximum limit of {0} approved attendance permissions for this month.", [max_allowed])
		});
		frm.set_value("permission_date", null);
	}
}

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