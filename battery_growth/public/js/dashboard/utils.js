(function registerDashboardUtils(root) {
  "use strict";

  const namespace =
    root.BatteryGrowthDashboardModules ||
    (root.BatteryGrowthDashboardModules = {});
  const numberFormatter = new Intl.NumberFormat("zh-CN", {
    maximumFractionDigits: 0,
  });
  const currencyFormatter = new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency: "CNY",
    maximumFractionDigits: 0,
  });

  function text(value) {
    return value === null || value === undefined ? "" : String(value);
  }

  function number(value) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function clampPercent(value) {
    return Math.max(0, Math.min(100, number(value)));
  }

  function isDashboardPayload(value) {
    return Boolean(
      value && typeof value === "object" && Array.isArray(value.periods),
    );
  }

  function briefForce(hasRenderedBrief) {
    return hasRenderedBrief ? 1 : 0;
  }

  namespace.utils = Object.freeze({
    briefForce,
    clampPercent,
    currency: (value) => currencyFormatter.format(number(value)),
    isDashboardPayload,
    number,
    numberLabel: (value) => numberFormatter.format(number(value)),
    text,
  });
})(globalThis);
