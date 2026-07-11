frappe.listview_settings["Attendance Permission"] = {
    add_fields: [
        "permission_type",
        "employee",
        "employee_name",
        "permission_date",
    ],
    has_indicator_for_draft: 1,
    get_indicator: function (doc) {
        const status_color = {
            Approved: "green",
            Rejected: "red",
            Open: "orange",
            Draft: "red",
            Cancelled: "red",
            Submitted: "blue",
        };
        const status =
            !doc.docstatus && ["Approved", "Rejected"].includes(doc.status) ? "Draft" : doc.status;
        return [__(status), status_color[status], "status,=," + doc.status];
    },
};