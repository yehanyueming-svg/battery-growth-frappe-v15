(function () {
  "use strict";

  const reportName = "User Growth Analysis";
  const drilldownFilters = [
    "customer_type",
    "province",
    "city",
    "service_plan",
    "acquisition_channel",
  ];

  function escapeAttribute(value) {
    return String(value).replace(
      /[&<>'"]/g,
      (character) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          "'": "&#39;",
          '"': "&quot;",
        })[character],
    );
  }

  function currentReportFilters() {
    const filters = {};
    drilldownFilters.forEach((fieldname) => {
      const value =
        frappe.query_report && frappe.query_report.get_filter_value(fieldname);
      if (value) {
        filters[fieldname] = value;
      }
    });
    return filters;
  }

  frappe.query_reports[reportName] = {
    filters: [
      {
        fieldname: "from_date",
        label: __("开始日期"),
        fieldtype: "Date",
        default: frappe.datetime.add_months(frappe.datetime.month_start(), -11),
        reqd: 1,
      },
      {
        fieldname: "to_date",
        label: __("结束日期"),
        fieldtype: "Date",
        default: frappe.datetime.get_today(),
        reqd: 1,
      },
      {
        fieldname: "granularity",
        label: __("粒度"),
        fieldtype: "Select",
        options: "Month\nWeek",
        default: "Month",
      },
      {
        fieldname: "customer_type",
        label: __("客户类型"),
        fieldtype: "Select",
        options: "\n个人\n企业",
      },
      { fieldname: "province", label: __("省份"), fieldtype: "Data" },
      { fieldname: "city", label: __("城市"), fieldtype: "Data" },
      {
        fieldname: "service_plan",
        label: __("服务套餐"),
        fieldtype: "Select",
        options: "\n基础换电\n畅换\n企业车队",
      },
      {
        fieldname: "acquisition_channel",
        label: __("获客渠道"),
        fieldtype: "Select",
        options: "\n直营网点\n企业合作\n渠道代理\n线上推广",
      },
    ],
    formatter(value, row, column, data, defaultFormatter) {
      const formatted = defaultFormatter(value, row, column, data);
      if (
        !data ||
        !Number(value) ||
        !["new_users", "churned_users"].includes(column.fieldname)
      ) {
        return formatted;
      }

      const dateField =
        column.fieldname === "new_users" ? "activation_date" : "churn_date";
      const status = column.fieldname === "churned_users" ? "已流失" : "";
      const attributes = [
        `data-date-field="${escapeAttribute(dateField)}"`,
        `data-from="${escapeAttribute(data.bucket_start)}"`,
        `data-to="${escapeAttribute(data.bucket_end)}"`,
      ];
      if (status) {
        attributes.push(`data-status="${escapeAttribute(status)}"`);
      }

      // Frappe's default formatter owns value rendering/escaping; retain its standard output.
      return `<a href="#" class="growth-drilldown" ${attributes.join(" ")}>${formatted}</a>`;
    },
  };

  $(document)
    .off("click.user-growth-analysis", ".growth-drilldown")
    .on("click.user-growth-analysis", ".growth-drilldown", (event) => {
      event.preventDefault();
      const $link = $(event.target).closest(".growth-drilldown");
      if (!$link.length) {
        return;
      }
      const dateField = $link.data("dateField");
      const fromDate = $link.data("from");
      const toDate = $link.data("to");
      const status = $link.data("status");
      const filters = {
        [dateField]: ["between", [fromDate, toDate]],
        ...currentReportFilters(),
      };
      if (status) {
        filters.service_status = status;
      }
      frappe.set_route("List", "Service Subscription", filters);
    });
})();
