/* eslint-env node */
"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const sourcePath = path.join(
  __dirname,
  "..",
  "battery_growth",
  "page",
  "battery_growth_dashboard",
  "battery_growth_dashboard.js",
);

function matches(element, selector) {
  if (selector.startsWith(".")) {
    return element.classList.contains(selector.slice(1));
  }
  if (selector.startsWith("#")) {
    return element.id === selector.slice(1);
  }
  const attribute = selector.match(/^\[([^=\]]+)(?:="([^"]*)")?\]$/);
  if (attribute) {
    return (
      element.hasAttribute(attribute[1]) &&
      (!attribute[2] || element.getAttribute(attribute[1]) === attribute[2])
    );
  }
  return element.tagName.toLowerCase() === selector.toLowerCase();
}

class FakeElement {
  constructor(tagName = "div") {
    this.tagName = tagName.toUpperCase();
    this.children = [];
    this.parentNode = null;
    this.attributes = new Map();
    this.listeners = new Map();
    this.style = {};
    this.className = "";
    this.disabled = false;
    this.value = "";
    this._text = "";
    this.classList = {
      add: (...names) => {
        const namesSet = new Set(this.className.split(/\s+/).filter(Boolean));
        names.forEach((name) => namesSet.add(name));
        this.className = [...namesSet].join(" ");
      },
      remove: (...names) => {
        const namesSet = new Set(this.className.split(/\s+/).filter(Boolean));
        names.forEach((name) => namesSet.delete(name));
        this.className = [...namesSet].join(" ");
      },
      contains: (name) => this.className.split(/\s+/).includes(name),
      toggle: (name, force) => {
        const shouldAdd =
          force === undefined ? !this.classList.contains(name) : force;
        if (shouldAdd) this.classList.add(name);
        else this.classList.remove(name);
        return shouldAdd;
      },
    };
  }

  set textContent(value) {
    this._text = String(value);
    this.children = [];
  }

  get textContent() {
    return (
      this._text + this.children.map((child) => child.textContent).join("")
    );
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
    if (name === "id") this.id = String(value);
    if (name === "class") this.className = String(value);
  }

  getAttribute(name) {
    return this.attributes.get(name) || null;
  }

  hasAttribute(name) {
    return this.attributes.has(name);
  }

  append(...nodes) {
    nodes.flat().forEach((node) => {
      if (!node) return;
      node.parentNode = this;
      this.children.push(node);
    });
  }

  appendChild(node) {
    this.append(node);
    return node;
  }

  replaceChildren(...nodes) {
    this.children = [];
    this._text = "";
    this.append(...nodes);
  }

  remove() {
    if (!this.parentNode) return;
    this.parentNode.children = this.parentNode.children.filter(
      (child) => child !== this,
    );
    this.parentNode = null;
  }

  addEventListener(name, callback) {
    this.listeners.set(name, callback);
  }

  removeEventListener(name, callback) {
    if (this.listeners.get(name) === callback) this.listeners.delete(name);
  }

  dispatch(name) {
    const callback = this.listeners.get(name);
    if (callback) callback({ preventDefault() {} });
  }

  querySelectorAll(selector) {
    const results = [];
    const walk = (node) => {
      node.children.forEach((child) => {
        if (matches(child, selector)) results.push(child);
        walk(child);
      });
    };
    walk(this);
    return results;
  }

  querySelector(selector) {
    return this.querySelectorAll(selector)[0] || null;
  }
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((onResolve, onReject) => {
    resolve = onResolve;
    reject = onReject;
  });
  return { promise, reject, resolve };
}

function dashboardData(label = "浙江省") {
  return {
    filters: { customer_type: "企业" },
    summary: {
      closing_active: 104,
      active_vehicles: 130,
      new_users: 15,
      churned_users: 4,
      net_growth: 11,
      churn_rate: 4,
    },
    periods: [
      {
        label: "2026-08",
        new_users: 15,
        churned_users: 4,
        closing_active: 104,
      },
    ],
    distributions: {
      regions: [{ label, value: 104, share: 100 }],
      customer_types: [{ label: "企业", value: 104, share: 100 }],
      plans: [{ label: "企业车队", value: 104, share: 100 }],
      churn_reasons: [{ label: "价格", value: 4, share: 100 }],
      stations: [{ label: "杭州站", value: 104, share: 100 }],
    },
    generated_at: "2026-09-03T10:30:00",
  };
}

function boot(callQueue = []) {
  const document = new FakeElement("document");
  document.hidden = false;
  document.createElement = (tagName) => new FakeElement(tagName);
  document.addEventListener = document.addEventListener.bind(document);
  document.removeEventListener = document.removeEventListener.bind(document);
  const timers = [];
  const charts = [];
  const fields = [];
  const page = {
    add_field(config) {
      const control = {
        get_value: () => control.value,
        set_value: (value) => {
          control.value = value;
        },
        value: config.default || "",
      };
      fields.push({ config, control });
      return control;
    },
    add_inner_button() {},
    main: new FakeElement("main"),
    set_title() {},
  };
  const context = {
    console,
    document,
    setTimeout,
    clearTimeout,
    window: {
      clearInterval(id) {
        id.cleared = true;
      },
      setInterval(callback, delay) {
        const timer = { callback, delay };
        timers.push(timer);
        return timer;
      },
    },
    frappe: {
      Chart: class {
        constructor(target, options) {
          this.target = target;
          this.options = options;
          this.destroyed = false;
          charts.push(this);
        }
        destroy() {
          this.destroyed = true;
        }
      },
      call(options) {
        const next = callQueue.shift();
        assert.ok(next, `unexpected API call to ${options.method}`);
        return next(options);
      },
      datetime: {
        add_months: () => "2025-10-01",
        get_today: () => "2026-09-03",
        month_start: () => "2026-09-01",
      },
      pages: {},
      ui: {
        make_app_page: ({ parent }) => {
          parent.append(page.main);
          return page;
        },
      },
    },
    __: (value) => value,
  };
  context.globalThis = context;
  vm.runInNewContext(fs.readFileSync(sourcePath, "utf8"), context, {
    filename: sourcePath,
  });
  const wrapper = new FakeElement("div");
  context.frappe.pages["battery-growth-dashboard"].on_page_load(wrapper);
  return {
    charts,
    context,
    dashboard: wrapper.batteryGrowthDashboard,
    document,
    fields,
    page,
    timers,
    wrapper,
  };
}

async function run() {
  assert.ok(
    fs.existsSync(sourcePath),
    "dashboard production controller is missing",
  );

  const first = boot([
    () => Promise.resolve({ message: dashboardData("<img src=x onerror=1>") }),
  ]);
  await first.dashboard.show();
  assert.equal(
    first.wrapper.querySelectorAll("[data-kpi]").length,
    6,
    `renders exactly six KPI nodes; rendered text: ${first.wrapper.textContent}`,
  );
  assert.equal(
    first.wrapper.querySelectorAll("img").length,
    0,
    "API labels are rendered as text, never markup",
  );
  assert.match(
    first.wrapper.textContent,
    /<img src=x onerror=1>/,
    "distribution text is retained safely",
  );
  assert.equal(
    first.charts.length,
    2,
    "uses the mixed trend and customer-type Frappe charts",
  );

  const older = deferred();
  const newer = deferred();
  const stale = boot([() => older.promise, () => newer.promise]);
  const oldRefresh = stale.dashboard.refresh();
  const newRefresh = stale.dashboard.refresh();
  newer.resolve({ message: dashboardData("最新区域") });
  await newRefresh;
  older.resolve({ message: dashboardData("过期区域") });
  await oldRefresh;
  assert.match(
    stale.wrapper.textContent,
    /最新区域/,
    "latest response renders",
  );
  assert.doesNotMatch(
    stale.wrapper.textContent,
    /过期区域/,
    "stale response cannot overwrite latest data",
  );

  const brief = boot([
    () => Promise.resolve({ message: dashboardData() }),
    (options) => {
      assert.equal(
        options.method,
        "battery_growth.api.dashboard.generate_operations_brief",
      );
      assert.equal(options.type, "POST");
      return Promise.resolve({
        message: {
          generated_at: "2026-09-03T10:31:00",
          source: "rules-fallback",
          summary: "模型不可用",
          insights: [
            {
              level: "info bg-insight-critical",
              title: "保持观察",
              evidence: "聚合指标正常",
              action: "继续监测",
            },
          ],
        },
      });
    },
  ]);
  await brief.dashboard.show();
  await brief.dashboard.loadBrief();
  assert.match(
    brief.wrapper.textContent,
    /规则回退/,
    "brief source is visible to operators",
  );
  assert.match(
    brief.wrapper.textContent,
    /2026-09-03T10:31:00/,
    "brief generation time is visible",
  );
  assert.equal(
    brief.wrapper.querySelectorAll(".bg-insight-critical").length,
    0,
    "untrusted insight levels cannot inject a severity class",
  );

  console.log("Dashboard browser contract: OK");
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
