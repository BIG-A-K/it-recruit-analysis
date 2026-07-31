import { metrics, type Metric } from "./data";

export const financialMetricKeys = [
  "revenue",
  "operating_profit",
  "net_cf",
  "operating_cf",
  "investing_cf",
  "financing_cf",
  "equity_ratio",
  "current_assets",
  "current_liabilities",
  "quick_assets",
];

export function financialMetricsForCompany(companyId: string): Metric[] {
  return metrics.filter(
    (metric) =>
      metric.company_id === companyId &&
      metric.availability === "reported" &&
      financialMetricKeys.includes(metric.metric_key),
  );
}
