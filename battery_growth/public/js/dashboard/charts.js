(function registerDashboardCharts(root) {
  "use strict";

  const namespace =
    root.BatteryGrowthDashboardModules ||
    (root.BatteryGrowthDashboardModules = {});
  const utils = namespace.utils;
  if (!utils || !namespace.DomView) {
    throw new Error("dashboard utils and DOM modules must load before charts");
  }

  class ChartManager {
    constructor(Chart, view, translate) {
      this.Chart = Chart;
      this.view = view;
      this.translate = translate;
      this.instances = [];
    }

    render(chartGrid, periods, distributions) {
      this.destroy();
      chartGrid.replaceChildren();
      const trend = this.view.panel(
        "trend",
        this.translate("用户增长趋势"),
        this.translate("柱：新增/流失；线：期末在服"),
      );
      const trendTarget = this.view.element("div", "bg-chart-target");
      trend.body.append(trendTarget);
      chartGrid.append(trend.panel);
      this.instances.push(
        new this.Chart(trendTarget, {
          type: "axis-mixed",
          height: 300,
          colors: ["#4ba3ff", "#f26d6d", "#5bcf9b"],
          data: {
            labels: periods.map((period) => utils.text(period.label)),
            datasets: [
              {
                name: this.translate("新增用户"),
                chartType: "bar",
                values: periods.map((period) => utils.number(period.new_users)),
              },
              {
                name: this.translate("流失用户"),
                chartType: "bar",
                values: periods.map((period) =>
                  utils.number(period.churned_users),
                ),
              },
              {
                name: this.translate("期末在服"),
                chartType: "line",
                values: periods.map((period) =>
                  utils.number(period.closing_active),
                ),
              },
            ],
          },
        }),
      );

      const customerTypes = this.view.panel(
        "customer-types",
        this.translate("客户类型结构"),
        this.translate("图例同时标示客户类型与数量"),
      );
      const customerEntries = distributions.customer_types || [];
      const customerTarget = this.view.element("div", "bg-chart-target");
      customerTypes.body.append(
        customerTarget,
        this.view.distributionList(customerEntries),
      );
      chartGrid.append(customerTypes.panel);
      this.instances.push(
        new this.Chart(customerTarget, {
          type: "donut",
          height: 220,
          colors: ["#4ba3ff", "#a889ff", "#f4c663"],
          data: {
            labels: customerEntries.map((entry) => utils.text(entry.label)),
            datasets: [
              {
                values: customerEntries.map((entry) =>
                  utils.number(entry.value),
                ),
              },
            ],
          },
        }),
      );

      [
        ["regions", "区域在服用户排名"],
        ["plans", "服务套餐分布"],
        ["churn_reasons", "流失原因"],
        ["stations", "换电站 TOP"],
      ].forEach(([key, title]) => {
        const panel = this.view.panel(
          key,
          this.translate(title),
          this.translate("文字、数量与占比"),
        );
        panel.body.append(this.view.distributionList(distributions[key] || []));
        chartGrid.append(panel.panel);
      });
    }

    destroy() {
      this.instances.forEach((chart) => {
        if (chart && typeof chart.destroy === "function") {
          chart.destroy();
        }
      });
      this.instances = [];
    }
  }

  namespace.ChartManager = ChartManager;
})(globalThis);
