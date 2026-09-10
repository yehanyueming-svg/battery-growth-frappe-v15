import "./dashboard/utils.js";
import "./dashboard/dom.js";
import "./dashboard/charts.js";
import "./dashboard/controller.js";

const modules = globalThis.BatteryGrowthDashboardModules;

globalThis.batteryGrowthDashboard = Object.freeze({
  create(wrapper) {
    return new modules.Controller(wrapper);
  },
});
