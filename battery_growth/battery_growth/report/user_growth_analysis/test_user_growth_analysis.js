"use strict";

/* eslint-env node */

const assert = require("node:assert/strict");

let delegatedClick;
const documentStub = {};
const activeFilters = {
  customer_type: "企业",
  province: "浙江省",
  city: "杭州市",
  service_plan: "企业车队",
  acquisition_channel: "企业合作",
};
const routes = [];

global.document = documentStub;
global.__ = (value) => value;
global.frappe = {
  query_reports: {},
  query_report: { get_filter_value: (fieldname) => activeFilters[fieldname] },
  datetime: {
    month_start: () => "2026-09-01",
    add_months: (_value, months) =>
      months === -11 ? "2025-10-01" : "unexpected",
    get_today: () => "2026-09-03",
  },
  set_route: (...args) => routes.push(args),
};
global.$ = (target) => {
  if (target === documentStub) {
    return {
      off: () => global.$(documentStub),
      on: (_eventName, selector, handler) => {
        assert.equal(selector, ".growth-drilldown");
        delegatedClick = handler;
        return global.$(documentStub);
      },
    };
  }
  return target;
};

require("./user_growth_analysis.js");

const report = frappe.query_reports["User Growth Analysis"];
assert.equal(report.filters[0].default, "2025-10-01");
assert.equal(report.filters[1].default, "2026-09-03");
assert.equal(report.filters[2].default, "Month");

const linked = report.formatter(
  42,
  null,
  { fieldname: "new_users" },
  { bucket_start: "2026-01-01", bucket_end: "2026-01-31" },
  (value) => `<span>${value}</span>`,
);
assert.match(linked, /data-date-field="activation_date"/);
assert.match(linked, /data-from="2026-01-01"/);
assert.match(linked, /data-to="2026-01-31"/);
assert.match(linked, /<span>42<\/span>/);

delegatedClick({
  preventDefault() {},
  target: {
    closest: () => ({
      length: 1,
      data: (name) =>
        ({
          dateField: "churn_date",
          from: "2026-01-01",
          to: "2026-01-31",
          status: "已流失",
        })[name],
    }),
  },
});
assert.deepEqual(routes, [
  [
    "List",
    "Service Subscription",
    {
      churn_date: ["between", ["2026-01-01", "2026-01-31"]],
      service_status: "已流失",
      ...activeFilters,
    },
  ],
]);

console.log("User Growth Analysis client contract passed");
