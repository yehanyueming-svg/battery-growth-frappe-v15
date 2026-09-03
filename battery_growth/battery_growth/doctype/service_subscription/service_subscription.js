frappe.ui.form.on("Service Subscription", {
  refresh(frm) {
    toggle_churn_fields(frm);
  },
  service_status(frm) {
    toggle_churn_fields(frm);
  },
  churn_reason(frm) {
    toggle_churn_fields(frm);
  },
  customer_type(frm) {
    if (frm.doc.customer_type === "个人") {
      frm.set_value("vehicle_count", 1);
    }
  },
});

function toggle_churn_fields(frm) {
  const is_churned = frm.doc.service_status === "已流失";
  frm.toggle_display("churn_date", is_churned);
  frm.toggle_display("churn_reason", is_churned);
  frm.toggle_display(
    "churn_note",
    is_churned && frm.doc.churn_reason === "其他",
  );
}
