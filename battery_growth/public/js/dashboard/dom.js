(function registerDashboardDom(root) {
  "use strict";

  const namespace =
    root.BatteryGrowthDashboardModules ||
    (root.BatteryGrowthDashboardModules = {});
  const utils = namespace.utils;
  if (!utils) {
    throw new Error("dashboard utils must load before the DOM module");
  }

  class DomView {
    constructor(documentObject, translate) {
      this.document = documentObject;
      this.translate = translate;
    }

    element(tagName, className, value) {
      const element = this.document.createElement(tagName);
      if (className) {
        element.className = className;
      }
      if (value !== undefined) {
        element.textContent = utils.text(value);
      }
      return element;
    }

    button(className, label, callback) {
      const button = this.element(
        "button",
        `btn btn-default ${className}`,
        label,
      );
      button.type = "button";
      button.addEventListener("click", callback);
      return button;
    }

    build(page, callbacks) {
      const rootElement = this.element("section", "bg-dashboard");
      rootElement.setAttribute(
        "aria-label",
        this.translate("智格换电运营态势"),
      );
      const status = this.element("div", "bg-status");
      status.setAttribute("role", "status");
      status.setAttribute("aria-live", "polite");
      const actions = this.element("div", "bg-actions");
      actions.setAttribute("aria-label", this.translate("仪表盘操作"));
      const kpis = this.element("div", "bg-kpis");
      kpis.setAttribute("aria-label", this.translate("核心指标"));
      const chartGrid = this.element("div", "bg-chart-grid");
      const aiBrief = this.element("section", "bg-ai-brief");
      aiBrief.setAttribute("aria-labelledby", "bg-ai-title");
      const briefHeader = this.element("header", "bg-ai-header");
      const briefTitle = this.element("h2", "", this.translate("AI 运营简报"));
      briefTitle.id = "bg-ai-title";
      const briefButton = this.button(
        "bg-generate-brief",
        this.translate("生成简报"),
        callbacks.loadBrief,
      );
      briefHeader.append(briefTitle, briefButton);
      const aiContent = this.element(
        "div",
        "bg-ai-content",
        this.translate("点击“生成简报”获取当前筛选条件下的运营简报。"),
      );
      aiBrief.append(briefHeader, aiContent);
      rootElement.append(status, actions, kpis, chartGrid, aiBrief);
      page.main.append(rootElement);

      const refreshButton = this.button(
        "bg-refresh",
        this.translate("刷新数据"),
        callbacks.refresh,
      );
      const autoRefreshButton = this.button(
        "bg-auto-refresh",
        this.translate("开启自动刷新"),
        callbacks.toggleAutoRefresh,
      );
      const fullscreenButton = this.button(
        "bg-fullscreen",
        this.translate("进入全屏"),
        callbacks.toggleFullscreen,
      );
      actions.append(refreshButton, autoRefreshButton, fullscreenButton);
      autoRefreshButton.setAttribute("aria-pressed", "false");
      fullscreenButton.setAttribute("aria-pressed", "false");
      return {
        actions,
        aiBrief,
        aiContent,
        autoRefreshButton,
        briefButton,
        chartGrid,
        fullscreenButton,
        kpis,
        refreshButton,
        root: rootElement,
        status,
      };
    }

    renderSummary(container, summary) {
      const metrics = [
        [
          "closing_active",
          "在服用户",
          utils.numberLabel(summary.closing_active),
          "active",
        ],
        [
          "active_vehicles",
          "服务车辆",
          utils.numberLabel(summary.active_vehicles),
          "active",
        ],
        [
          "new_users",
          "本期新增",
          utils.numberLabel(summary.new_users),
          "positive",
        ],
        [
          "churned_users",
          "本期流失",
          utils.numberLabel(summary.churned_users),
          "critical",
        ],
        [
          "net_growth",
          "净增长",
          utils.numberLabel(summary.net_growth),
          utils.number(summary.net_growth) < 0 ? "critical" : "positive",
        ],
        [
          "churn_rate",
          "流失率",
          `${utils.number(summary.churn_rate).toFixed(2)}%`,
          "critical",
        ],
      ];
      const cards = metrics.map(([key, label, value, tone]) => {
        const card = this.element("article", `bg-kpi bg-kpi-${tone}`);
        card.setAttribute("data-kpi", key);
        card.append(
          this.element("p", "bg-kpi-label", this.translate(label)),
          this.element("strong", "bg-kpi-value", value),
        );
        return card;
      });
      container.replaceChildren(...cards);
    }

    panel(key, title, description) {
      const panel = this.element("section", `bg-panel bg-panel-${key}`);
      const heading = this.element("header", "bg-panel-header");
      heading.append(
        this.element("h2", "", title),
        this.element("p", "bg-panel-description", description),
      );
      const body = this.element("div", "bg-panel-body");
      panel.append(heading, body);
      return { body, panel };
    }

    distributionList(entries) {
      const list = this.element("ul", "bg-distribution-list");
      if (!entries.length) {
        list.append(
          this.element("li", "bg-list-empty", this.translate("暂无分布数据")),
        );
        return list;
      }
      entries.forEach((entry) => {
        const item = this.element("li", "bg-distribution-item");
        const values = this.element("span", "bg-distribution-values");
        values.append(
          this.element("strong", "", utils.numberLabel(entry.value)),
          this.element("span", "", ` ${utils.number(entry.share).toFixed(2)}%`),
        );
        const track = this.element("div", "bg-distribution-track");
        track.setAttribute("aria-hidden", "true");
        const fill = this.element("div", "bg-distribution-fill");
        fill.style.width = `${utils.clampPercent(entry.share)}%`;
        track.append(fill);
        item.append(
          this.element("span", "bg-distribution-label", entry.label),
          values,
          track,
        );
        list.append(item);
      });
      return list;
    }

    renderEmpty(kpis, chartGrid) {
      kpis.replaceChildren();
      chartGrid.replaceChildren(
        this.element(
          "section",
          "bg-empty",
          this.translate(
            "当前筛选条件下暂无可展示的运营数据。请调整日期或筛选条件后重试。",
          ),
        ),
      );
    }

    renderError(kpis, chartGrid, retry) {
      kpis.replaceChildren();
      const error = this.element("section", "bg-error");
      error.append(
        this.element(
          "p",
          "",
          this.translate("加载运营数据失败。请检查网络或权限后重试。"),
        ),
        this.button("bg-retry", this.translate("重试"), retry),
      );
      chartGrid.replaceChildren(error);
    }

    setBriefMessage(container, className, message) {
      container.replaceChildren(this.element("p", className, message));
    }

    renderBrief(container, brief) {
      const sourceLabels = {
        rules: this.translate("规则分析"),
        "openai-compatible": this.translate("AI 生成"),
        "rules-fallback": this.translate("规则回退"),
      };
      const content = this.element("div", "bg-brief-result");
      const meta = this.element("p", "bg-brief-meta");
      meta.append(
        this.element(
          "strong",
          "",
          sourceLabels[brief.source] || sourceLabels.rules,
        ),
        this.element(
          "span",
          "",
          brief.generated_at ? ` · ${utils.text(brief.generated_at)}` : "",
        ),
      );
      content.append(meta);
      if (brief.summary) {
        content.append(this.element("p", "bg-brief-summary", brief.summary));
      }
      const insights = Array.isArray(brief.insights) ? brief.insights : [];
      const list = this.element("ul", "bg-insight-list");
      insights.forEach((insight) => {
        const level = ["info", "warning", "critical"].includes(insight.level)
          ? insight.level
          : "info";
        const item = this.element("li", `bg-insight bg-insight-${level}`);
        item.append(
          this.element("strong", "", insight.title),
          this.element("p", "", insight.evidence),
          this.element("p", "bg-insight-action", insight.action),
        );
        list.append(item);
      });
      if (!insights.length) {
        list.append(
          this.element(
            "li",
            "bg-list-empty",
            this.translate("暂无可展示的运营洞察"),
          ),
        );
      }
      content.append(list);
      container.replaceChildren(content);
    }
  }

  namespace.DomView = DomView;
})(globalThis);
