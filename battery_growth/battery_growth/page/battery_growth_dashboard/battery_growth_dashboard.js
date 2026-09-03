(function () {
  "use strict";

  const PAGE_NAME = "battery-growth-dashboard";
  const REFRESH_INTERVAL_MS = 5 * 60 * 1000;
  const SOURCE_LABELS = {
    rules: __("规则分析"),
    "openai-compatible": __("AI 生成"),
    "rules-fallback": __("规则回退"),
  };
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

  function makeElement(tagName, className, value) {
    const element = document.createElement(tagName);
    if (className) {
      element.className = className;
    }
    if (value !== undefined) {
      element.textContent = text(value);
    }
    return element;
  }

  class BatteryGrowthDashboard {
    constructor(wrapper) {
      this.wrapper = wrapper;
      this.filters = {};
      this.filterControls = {};
      this.charts = [];
      this.refreshTimer = null;
      this.requestSerial = 0;
      this.briefRequestSerial = 0;
      this.filterSnapshot = null;
      this.autoRefreshEnabled = false;
      this.destroyed = false;
      this.onFullscreenChange = this.syncFullscreenLabel.bind(this);
      this.onWrapperHide = this.hide.bind(this);
      this.$wrapper = $(wrapper);
      document.addEventListener("fullscreenchange", this.onFullscreenChange);
      this.$wrapper.on("hide.battery-growth-dashboard", this.onWrapperHide);
      this.makePage();
      this.makeFilters();
    }

    makePage() {
      this.page = frappe.ui.make_app_page({
        parent: this.wrapper,
        title: __("智格换电运营态势"),
        single_column: true,
      });
      this.root = makeElement("section", "bg-dashboard");
      this.root.setAttribute("aria-label", __("智格换电运营态势"));
      this.status = makeElement("div", "bg-status");
      this.status.setAttribute("role", "status");
      this.status.setAttribute("aria-live", "polite");
      this.actions = makeElement("div", "bg-actions");
      this.actions.setAttribute("aria-label", __("仪表盘操作"));
      this.kpis = makeElement("div", "bg-kpis");
      this.kpis.setAttribute("aria-label", __("核心指标"));
      this.chartGrid = makeElement("div", "bg-chart-grid");
      this.aiBrief = makeElement("section", "bg-ai-brief");
      this.aiBrief.setAttribute("aria-labelledby", "bg-ai-title");
      const briefHeader = makeElement("header", "bg-ai-header");
      const briefTitle = makeElement("h2", "", __("AI 运营简报"));
      briefTitle.id = "bg-ai-title";
      this.briefButton = this.makeButton(
        "bg-generate-brief",
        __("重新生成"),
        () => this.loadBrief(),
      );
      briefHeader.append(briefTitle, this.briefButton);
      this.aiContent = makeElement(
        "div",
        "bg-ai-content",
        __("点击“重新生成”获取当前筛选条件下的运营简报。"),
      );
      this.aiBrief.append(briefHeader, this.aiContent);
      this.root.append(
        this.status,
        this.actions,
        this.kpis,
        this.chartGrid,
        this.aiBrief,
      );
      this.page.main.empty().append(this.root);
      this.refreshButton = this.makeButton("bg-refresh", __("刷新数据"), () =>
        this.refresh(),
      );
      this.autoRefreshButton = this.makeButton(
        "bg-auto-refresh",
        __("开启自动刷新"),
        () => this.toggleAutoRefresh(),
      );
      this.fullscreenButton = this.makeButton(
        "bg-fullscreen",
        __("进入全屏"),
        () => this.toggleFullscreen(),
      );
      this.actions.append(
        this.refreshButton,
        this.autoRefreshButton,
        this.fullscreenButton,
      );
      this.autoRefreshButton.setAttribute("aria-pressed", "false");
      this.fullscreenButton.setAttribute("aria-pressed", "false");
    }

    makeButton(className, label, callback) {
      const button = makeElement(
        "button",
        `btn btn-default ${className}`,
        label,
      );
      button.type = "button";
      button.addEventListener("click", callback);
      return button;
    }

    makeFilters() {
      const fields = [
        {
          fieldname: "from_date",
          label: __("开始日期"),
          fieldtype: "Date",
          default: frappe.datetime.add_months(
            frappe.datetime.month_start(),
            -11,
          ),
        },
        {
          fieldname: "to_date",
          label: __("结束日期"),
          fieldtype: "Date",
          default: frappe.datetime.get_today(),
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
          fieldname: "granularity",
          label: __("粒度"),
          fieldtype: "Select",
          options: "Month\nWeek",
          default: "Month",
        },
      ];
      fields.forEach((definition) => {
        const control = this.page.add_field({
          ...definition,
          change: () => this.refresh(),
        });
        this.filterControls[definition.fieldname] = control;
      });
    }

    getFilters() {
      const filters = {};
      Object.entries(this.filterControls).forEach(([fieldname, control]) => {
        const value = control.get_value();
        if (value) {
          filters[fieldname] = value;
        }
      });
      this.filters = filters;
      return filters;
    }

    getFilterRequest() {
      const filters = this.getFilters();
      return { filters, snapshot: JSON.stringify(filters) };
    }

    invalidateBrief() {
      this.briefRequestSerial += 1;
      this.aiContent.replaceChildren(
        makeElement(
          "p",
          "bg-brief-pending",
          __("筛选条件已变更，请重新生成运营简报。"),
        ),
      );
    }

    show() {
      if (this.destroyed) {
        return Promise.resolve();
      }
      this.startAutoRefresh();
      return this.refresh();
    }

    hide() {
      this.stopAutoRefresh();
    }

    async refresh() {
      if (this.destroyed || document.hidden) {
        return;
      }
      const filterRequest = this.getFilterRequest();
      if (this.filterSnapshot !== filterRequest.snapshot) {
        this.filterSnapshot = filterRequest.snapshot;
        this.invalidateBrief();
      }
      const serial = ++this.requestSerial;
      this.refreshButton.disabled = true;
      this.setStatus(__("正在加载聚合运营数据…"));
      try {
        const response = await Promise.resolve(
          frappe.call({
            method: "battery_growth.api.dashboard.get_dashboard_data",
            args: { filters: filterRequest.snapshot },
            freeze: false,
          }),
        );
        if (serial !== this.requestSerial || this.destroyed) {
          return;
        }
        const data = response && response.message;
        if (!data || !Array.isArray(data.periods)) {
          throw new Error("dashboard response is missing periods");
        }
        this.latestData = data;
        if (!data.periods.length) {
          this.renderEmpty();
          return;
        }
        this.renderSummary(data.summary || {});
        this.renderCharts(data.periods, data.distributions || {});
        const updated = data.generated_at
          ? ` · ${text(data.generated_at)}`
          : "";
        const revenue = data.summary && data.summary.monthly_revenue;
        const revenueLabel =
          revenue === undefined
            ? ""
            : ` · ${__("在服月服务费")} ${currencyFormatter.format(number(revenue))}`;
        this.setStatus(`${__("数据已更新")}${updated}${revenueLabel}`);
      } catch (error) {
        if (serial === this.requestSerial && !this.destroyed) {
          this.renderError(error);
        }
      } finally {
        if (serial === this.requestSerial && !this.destroyed) {
          this.refreshButton.disabled = false;
        }
      }
    }

    renderSummary(summary) {
      const metrics = [
        {
          key: "closing_active",
          label: __("在服用户"),
          value: numberFormatter.format(number(summary.closing_active)),
          tone: "active",
        },
        {
          key: "active_vehicles",
          label: __("服务车辆"),
          value: numberFormatter.format(number(summary.active_vehicles)),
          tone: "active",
        },
        {
          key: "new_users",
          label: __("本期新增"),
          value: numberFormatter.format(number(summary.new_users)),
          tone: "positive",
        },
        {
          key: "churned_users",
          label: __("本期流失"),
          value: numberFormatter.format(number(summary.churned_users)),
          tone: "critical",
        },
        {
          key: "net_growth",
          label: __("净增长"),
          value: numberFormatter.format(number(summary.net_growth)),
          tone: number(summary.net_growth) < 0 ? "critical" : "positive",
        },
        {
          key: "churn_rate",
          label: __("流失率"),
          value: `${number(summary.churn_rate).toFixed(2)}%`,
          tone: "critical",
        },
      ];
      const cards = metrics.map((metric) => {
        const card = makeElement("article", `bg-kpi bg-kpi-${metric.tone}`);
        card.setAttribute("data-kpi", metric.key);
        card.append(
          makeElement("p", "bg-kpi-label", metric.label),
          makeElement("strong", "bg-kpi-value", metric.value),
        );
        return card;
      });
      this.kpis.replaceChildren(...cards);
    }

    renderCharts(periods, distributions) {
      this.destroyCharts();
      this.chartGrid.replaceChildren();
      const trend = this.makePanel(
        "trend",
        __("用户增长趋势"),
        __("柱：新增/流失；线：期末在服"),
      );
      const trendTarget = makeElement("div", "bg-chart-target");
      trend.body.append(trendTarget);
      this.chartGrid.append(trend.panel);
      this.charts.push(
        new frappe.Chart(trendTarget, {
          type: "axis-mixed",
          height: 300,
          colors: ["#4ba3ff", "#f26d6d", "#5bcf9b"],
          data: {
            labels: periods.map((period) => text(period.label)),
            datasets: [
              {
                name: __("新增用户"),
                chartType: "bar",
                values: periods.map((period) => number(period.new_users)),
              },
              {
                name: __("流失用户"),
                chartType: "bar",
                values: periods.map((period) => number(period.churned_users)),
              },
              {
                name: __("期末在服"),
                chartType: "line",
                values: periods.map((period) => number(period.closing_active)),
              },
            ],
          },
        }),
      );
      const customerTypes = this.makePanel(
        "customer-types",
        __("客户类型结构"),
        __("图例同时标示客户类型与数量"),
      );
      const customerTarget = makeElement("div", "bg-chart-target");
      customerTypes.body.append(
        customerTarget,
        this.makeDistributionList(distributions.customer_types || []),
      );
      this.chartGrid.append(customerTypes.panel);
      this.charts.push(
        new frappe.Chart(customerTarget, {
          type: "donut",
          height: 220,
          colors: ["#4ba3ff", "#a889ff", "#f4c663"],
          data: {
            labels: (distributions.customer_types || []).map((entry) =>
              text(entry.label),
            ),
            datasets: [
              {
                values: (distributions.customer_types || []).map((entry) =>
                  number(entry.value),
                ),
              },
            ],
          },
        }),
      );
      [
        ["regions", __("区域在服用户排名")],
        ["plans", __("服务套餐分布")],
        ["churn_reasons", __("流失原因")],
        ["stations", __("换电站 TOP")],
      ].forEach(([key, title]) => {
        const panel = this.makePanel(key, title, __("文字、数量与占比"));
        panel.body.append(this.makeDistributionList(distributions[key] || []));
        this.chartGrid.append(panel.panel);
      });
    }

    makePanel(key, title, description) {
      const panel = makeElement("section", `bg-panel bg-panel-${key}`);
      const heading = makeElement("header", "bg-panel-header");
      heading.append(
        makeElement("h2", "", title),
        makeElement("p", "bg-panel-description", description),
      );
      const body = makeElement("div", "bg-panel-body");
      panel.append(heading, body);
      return { body, panel };
    }

    makeDistributionList(entries) {
      const list = makeElement("ul", "bg-distribution-list");
      if (!entries.length) {
        list.append(makeElement("li", "bg-list-empty", __("暂无分布数据")));
        return list;
      }
      entries.forEach((entry) => {
        const item = makeElement("li", "bg-distribution-item");
        const label = makeElement("span", "bg-distribution-label", entry.label);
        const values = makeElement("span", "bg-distribution-values");
        values.append(
          makeElement(
            "strong",
            "",
            numberFormatter.format(number(entry.value)),
          ),
          makeElement("span", "", ` ${number(entry.share).toFixed(2)}%`),
        );
        const track = makeElement("div", "bg-distribution-track");
        track.setAttribute("aria-hidden", "true");
        const fill = makeElement("div", "bg-distribution-fill");
        fill.style.width = `${Math.max(0, Math.min(100, number(entry.share)))}%`;
        track.append(fill);
        item.append(label, values, track);
        list.append(item);
      });
      return list;
    }

    renderEmpty() {
      this.destroyCharts();
      this.kpis.replaceChildren();
      this.chartGrid.replaceChildren(
        makeElement(
          "section",
          "bg-empty",
          __(
            "当前筛选条件下暂无可展示的运营数据。请调整日期或筛选条件后重试。",
          ),
        ),
      );
      this.setStatus(__("暂无运营数据"));
    }

    renderError() {
      this.destroyCharts();
      this.kpis.replaceChildren();
      const error = makeElement("section", "bg-error");
      const retry = this.makeButton("bg-retry", __("重试"), () =>
        this.refresh(),
      );
      error.append(
        makeElement("p", "", __("加载运营数据失败。请检查网络或权限后重试。")),
        retry,
      );
      this.chartGrid.replaceChildren(error);
      this.setStatus(__("加载失败"));
    }

    toggleAutoRefresh() {
      this.autoRefreshEnabled = !this.autoRefreshEnabled;
      if (this.autoRefreshEnabled) {
        this.startAutoRefresh();
      } else {
        this.stopAutoRefresh();
      }
      this.autoRefreshButton.textContent = this.autoRefreshEnabled
        ? __("关闭自动刷新")
        : __("开启自动刷新");
      this.autoRefreshButton.setAttribute(
        "aria-pressed",
        String(this.autoRefreshEnabled),
      );
      this.setStatus(
        this.autoRefreshEnabled
          ? __("已开启每 5 分钟自动刷新")
          : __("已关闭自动刷新"),
      );
    }

    startAutoRefresh() {
      if (!this.autoRefreshEnabled || this.refreshTimer || this.destroyed) {
        return;
      }
      this.refreshTimer = window.setInterval(() => {
        if (!document.hidden) {
          this.refresh();
        }
      }, REFRESH_INTERVAL_MS);
    }

    stopAutoRefresh() {
      if (this.refreshTimer) {
        window.clearInterval(this.refreshTimer);
        this.refreshTimer = null;
      }
    }

    async toggleFullscreen() {
      const isFullscreen = document.fullscreenElement === this.root;
      const action = isFullscreen
        ? document.exitFullscreen
        : this.root.requestFullscreen;
      const target = isFullscreen ? document : this.root;
      if (typeof action !== "function") {
        this.setStatus(__("当前浏览器不支持全屏模式。"));
        return;
      }
      try {
        await Promise.resolve(action.call(target));
      } catch (error) {
        this.setStatus(
          isFullscreen
            ? __("无法退出全屏，请稍后重试。")
            : __("无法进入全屏，请检查浏览器权限后重试。"),
        );
      }
    }

    syncFullscreenLabel() {
      const isFullscreen = document.fullscreenElement === this.root;
      this.root.classList.toggle("bg-is-fullscreen", isFullscreen);
      this.fullscreenButton.textContent = isFullscreen
        ? __("退出全屏")
        : __("进入全屏");
      this.fullscreenButton.setAttribute("aria-pressed", String(isFullscreen));
    }

    async loadBrief() {
      if (this.destroyed) {
        return;
      }
      const filterRequest = this.getFilterRequest();
      if (this.filterSnapshot !== filterRequest.snapshot) {
        this.filterSnapshot = filterRequest.snapshot;
      }
      const dashboardRequestSerial = this.requestSerial;
      const briefRequestSerial = ++this.briefRequestSerial;
      this.briefButton.disabled = true;
      this.aiContent.replaceChildren(
        makeElement("p", "bg-brief-loading", __("正在生成运营简报…")),
      );
      try {
        const response = await Promise.resolve(
          frappe.call({
            method: "battery_growth.api.dashboard.generate_operations_brief",
            type: "POST",
            args: { filters: filterRequest.snapshot, force: 1 },
            freeze: false,
          }),
        );
        if (
          this.destroyed ||
          briefRequestSerial !== this.briefRequestSerial ||
          dashboardRequestSerial !== this.requestSerial ||
          filterRequest.snapshot !== this.filterSnapshot
        ) {
          return;
        }
        this.renderBrief((response && response.message) || {});
      } catch (error) {
        if (!this.destroyed && briefRequestSerial === this.briefRequestSerial) {
          this.aiContent.replaceChildren(
            makeElement(
              "p",
              "bg-brief-error",
              __("简报生成失败，请稍后重试。"),
            ),
          );
        }
      } finally {
        if (!this.destroyed && briefRequestSerial === this.briefRequestSerial) {
          this.briefButton.disabled = false;
        }
      }
    }

    renderBrief(brief) {
      const source = SOURCE_LABELS[brief.source] || __("规则分析");
      const content = makeElement("div", "bg-brief-result");
      const meta = makeElement("p", "bg-brief-meta");
      meta.append(
        makeElement("strong", "", source),
        makeElement(
          "span",
          "",
          brief.generated_at ? ` · ${text(brief.generated_at)}` : "",
        ),
      );
      content.append(meta);
      if (brief.summary) {
        content.append(makeElement("p", "bg-brief-summary", brief.summary));
      }
      const insights = Array.isArray(brief.insights) ? brief.insights : [];
      const list = makeElement("ul", "bg-insight-list");
      insights.forEach((insight) => {
        const level = ["info", "warning", "critical"].includes(insight.level)
          ? insight.level
          : "info";
        const item = makeElement("li", `bg-insight bg-insight-${level}`);
        item.append(
          makeElement("strong", "", insight.title),
          makeElement("p", "", insight.evidence),
          makeElement("p", "bg-insight-action", insight.action),
        );
        list.append(item);
      });
      if (!insights.length) {
        list.append(
          makeElement("li", "bg-list-empty", __("暂无可展示的运营洞察")),
        );
      }
      content.append(list);
      this.aiContent.replaceChildren(content);
    }

    destroyCharts() {
      this.charts.forEach((chart) => {
        if (chart && typeof chart.destroy === "function") {
          chart.destroy();
        }
      });
      this.charts = [];
    }

    setStatus(message) {
      this.status.textContent = text(message);
    }

    destroy() {
      if (this.destroyed) {
        return;
      }
      this.destroyed = true;
      this.stopAutoRefresh();
      this.destroyCharts();
      document.removeEventListener("fullscreenchange", this.onFullscreenChange);
      this.$wrapper.off("hide.battery-growth-dashboard", this.onWrapperHide);
    }
  }

  frappe.pages[PAGE_NAME] = frappe.pages[PAGE_NAME] || {};
  frappe.pages[PAGE_NAME].on_page_load = (wrapper) => {
    if (wrapper.batteryGrowthDashboard) {
      wrapper.batteryGrowthDashboard.destroy();
    }
    wrapper.batteryGrowthDashboard = new BatteryGrowthDashboard(wrapper);
  };
  frappe.pages[PAGE_NAME].on_page_show = (wrapper) =>
    wrapper.batteryGrowthDashboard.show();
})();
