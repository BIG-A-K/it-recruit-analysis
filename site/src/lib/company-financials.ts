import { metrics, type Metric } from "./data";

export const financialMetricKeys = [
  "revenue",
  "operating_profit",
  "business_profit",
  "net_cf",
  "operating_cf",
  "investing_cf",
  "financing_cf",
  "equity_ratio",
  "current_assets",
  "current_liabilities",
  "quick_assets",
];

const trendMetricKeys = [...financialMetricKeys, "average_annual_salary"];

export function financialMetricsForCompany(companyId: string): Metric[] {
  return metrics.filter(
    (metric) =>
      metric.company_id === companyId &&
      metric.availability === "reported" &&
      financialMetricKeys.includes(metric.metric_key),
  );
}

export function trendMetricsForCompany(companyId: string): Metric[] {
  return metrics.filter(
    (metric) =>
      metric.company_id === companyId &&
      metric.availability === "reported" &&
      trendMetricKeys.includes(metric.metric_key),
  );
}
