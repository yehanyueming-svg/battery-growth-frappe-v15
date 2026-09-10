/* eslint-env node */
"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const moduleRoot = path.join(__dirname, "..", "public", "js", "dashboard");
const moduleFiles = ["utils.js", "dom.js", "charts.js", "controller.js"];
const context = { console, Intl };
context.globalThis = context;

for (const filename of moduleFiles) {
  const sourcePath = path.join(moduleRoot, filename);
  assert.ok(
    fs.existsSync(sourcePath),
    `dashboard module is missing: ${filename}`,
  );
  vm.runInNewContext(fs.readFileSync(sourcePath, "utf8"), context, {
    filename: sourcePath,
  });
}

const modules = context.BatteryGrowthDashboardModules;
assert.ok(modules, "dashboard module namespace is registered");
assert.ok(modules.DomView, "DOM view module is registered");
assert.ok(modules.ChartManager, "chart module is registered");
assert.ok(modules.Controller, "controller module is registered");
assert.equal(modules.utils.text(null), "");
assert.equal(modules.utils.text(42), "42");
assert.equal(modules.utils.number("invalid"), 0);
assert.equal(modules.utils.number("12"), 12);
assert.equal(modules.utils.clampPercent(-1), 0);
assert.equal(modules.utils.clampPercent(120), 100);
assert.equal(modules.utils.isDashboardPayload({ periods: [] }), true);
assert.equal(modules.utils.isDashboardPayload({ periods: {} }), false);
assert.equal(modules.utils.briefForce(false), 0);
assert.equal(modules.utils.briefForce(true), 1);

console.log("Dashboard modules: OK");
