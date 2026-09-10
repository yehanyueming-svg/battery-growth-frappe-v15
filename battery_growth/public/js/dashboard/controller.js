(function registerDashboardController(root) {
  "use strict";

  const namespace =
    root.BatteryGrowthDashboardModules ||
    (root.BatteryGrowthDashboardModules = {});
  const { ChartManager, DomView, utils } = namespace;
  if (!ChartManager || !DomView || !utils) {
    throw new Error("dashboard modules loaded in the wrong order");
  }

  const REFRESH_INTERVAL_MS = 5 * 60 * 1000;

  class BatteryGrowthDashboard {
    constructor(wrapper) {
      this.wrapper = wrapper;
      this.filters = {};
      this.filterControls = {};
      this.refreshTimer = null;
      this.requestSerial = 0;
      this.briefRequestSerial = 0;
      this.filterSnapshot = null;
      this.autoRefreshEnabled = false;
      this.hasRenderedBrief = false;
      this.destroyed = false;
      this.onFullscreenChange = this.syncFullscreenLabel.bind(this);
      this.onWrapperHide = this.hide.bind(this);
      this.$wrapper = $(wrapper);
      this.view = new DomView(document, __);
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
      Object.assign(
        this,
        this.view.build(this.page, {
          loadBrief: () => this.loadBrief(),
          refresh: () => this.refresh(),
          toggleAutoRefresh: () => this.toggleAutoRefresh(),
          toggleFullscreen: () => this.toggleFullscreen(),
        }),
      );
      this.chartManager = new ChartManager(frappe.Chart, this.view, __);
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
          fieldname: "acquisition_channel",
          label: __("获客渠道"),
          fieldtype: "Select",
          options: "\n直营网点\n企业合作\n渠道代理\n线上推广",
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
        this.filterControls[definition.fieldname] = this.page.add_field({
          ...definition,
          change: () => this.refresh(),
        });
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

    invalidateBrief(message) {
      this.briefRequestSerial += 1;
      this.hasRenderedBrief = false;
      this.briefButton.disabled = false;
      this.briefButton.textContent = __("生成简报");
      this.view.setBriefMessage(
        this.aiContent,
        "bg-brief-pending",
        message || __("运营数据已刷新，请重新生成运营简报。"),
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
      const filtersChanged = this.filterSnapshot !== filterRequest.snapshot;
      this.filterSnapshot = filterRequest.snapshot;
      this.invalidateBrief(
        filtersChanged ? __("筛选条件已变更，请重新生成运营简报。") : undefined,
      );
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
        if (!utils.isDashboardPayload(data)) {
          throw new Error("dashboard response is missing periods");
        }
        this.latestData = data;
        const summary = data.summary || {};
        const hasOperationalData = [
          "opening_active",
          "closing_active",
          "new_users",
          "churned_users",
        ].some((key) => utils.number(summary[key]) !== 0);
        if (!data.periods.length || !hasOperationalData) {
          this.renderEmpty();
          return;
        }
        this.view.renderSummary(this.kpis, summary);
        this.chartManager.render(
          this.chartGrid,
          data.periods,
          data.distributions || {},
        );
        const updated = data.generated_at
          ? ` · ${utils.text(data.generated_at)}`
          : "";
        const revenueLabel =
          summary.monthly_revenue === undefined
            ? ""
            : ` · ${__("在服月服务费")} ${utils.currency(summary.monthly_revenue)}`;
        this.setStatus(`${__("数据已更新")}${updated}${revenueLabel}`);
      } catch (error) {
        if (serial === this.requestSerial && !this.destroyed) {
          this.renderError();
        }
      } finally {
        if (serial === this.requestSerial && !this.destroyed) {
          this.refreshButton.disabled = false;
        }
      }
    }

    renderEmpty() {
      this.chartManager.destroy();
      this.view.renderEmpty(this.kpis, this.chartGrid);
      this.setStatus(__("暂无运营数据"));
    }

    renderError() {
      this.chartManager.destroy();
      this.view.renderError(this.kpis, this.chartGrid, () => this.refresh());
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
      const force = utils.briefForce(this.hasRenderedBrief);
      const dashboardRequestSerial = this.requestSerial;
      const briefRequestSerial = ++this.briefRequestSerial;
      this.briefButton.disabled = true;
      this.view.setBriefMessage(
        this.aiContent,
        "bg-brief-loading",
        __("正在生成运营简报…"),
      );
      try {
        const response = await Promise.resolve(
          frappe.call({
            method: "battery_growth.api.dashboard.generate_operations_brief",
            type: "POST",
            args: { filters: filterRequest.snapshot, force },
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
        this.view.renderBrief(
          this.aiContent,
          (response && response.message) || {},
        );
        this.hasRenderedBrief = true;
        this.briefButton.textContent = __("重新生成");
      } catch (error) {
        if (!this.destroyed && briefRequestSerial === this.briefRequestSerial) {
          this.hasRenderedBrief = false;
          this.briefButton.textContent = __("生成简报");
          this.view.setBriefMessage(
            this.aiContent,
            "bg-brief-error",
            __("简报生成失败，请稍后重试。"),
          );
        }
      } finally {
        if (!this.destroyed && briefRequestSerial === this.briefRequestSerial) {
          this.briefButton.disabled = false;
        }
      }
    }

    setStatus(message) {
      this.status.textContent = utils.text(message);
    }

    destroy() {
      if (this.destroyed) {
        return;
      }
      this.destroyed = true;
      this.stopAutoRefresh();
      this.chartManager.destroy();
      document.removeEventListener("fullscreenchange", this.onFullscreenChange);
      this.$wrapper.off("hide.battery-growth-dashboard", this.onWrapperHide);
    }
  }

  namespace.Controller = BatteryGrowthDashboard;
})(globalThis);
