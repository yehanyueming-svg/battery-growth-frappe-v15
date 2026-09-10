(function registerBatteryGrowthPage() {
  "use strict";

  const PAGE_NAME = "battery-growth-dashboard";
  const BUNDLE_NAME = "battery_growth_dashboard.bundle.js";

  function loadDashboard(wrapper) {
    if (!wrapper.batteryGrowthDashboardLoading) {
      wrapper.batteryGrowthDashboardLoading = frappe
        .require(BUNDLE_NAME)
        .then(() => {
          if (wrapper.batteryGrowthDashboard) {
            wrapper.batteryGrowthDashboard.destroy();
          }
          wrapper.batteryGrowthDashboard =
            globalThis.batteryGrowthDashboard.create(wrapper);
        });
    }
    return wrapper.batteryGrowthDashboardLoading;
  }

  frappe.pages[PAGE_NAME] = frappe.pages[PAGE_NAME] || {};
  frappe.pages[PAGE_NAME].on_page_load = (wrapper) => loadDashboard(wrapper);
  frappe.pages[PAGE_NAME].on_page_show = (wrapper) =>
    Promise.resolve(loadDashboard(wrapper)).then(() =>
      wrapper.batteryGrowthDashboard.show(),
    );
})();
