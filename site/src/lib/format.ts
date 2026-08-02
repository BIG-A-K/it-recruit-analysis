export const metricLabels: Record<string, string> = {
  average_annual_salary: "平均年間給与",
  net_cf: "ネットCF",
  operating_profit: "営業利益",
  business_profit: "事業利益",
  average_tenure: "平均勤続年数",
  average_age: "平均年齢",
  revenue: "売上収益",
  equity_ratio: "自己資本比率",
  operating_cf: "営業CF",
  investing_cf: "投資CF",
  financing_cf: "財務CF",
  current_assets: "流動資産",
  current_liabilities: "流動負債",
  current_ratio: "流動比率",
  quick_assets: "当座資産",
  total_funding: "累計資金調達額",
  employee_count: "従業員数",
};

export const metricDisplayOrder = Object.keys(metricLabels);

export function formatValue(
  value: number,
  unit: string,
  metricKey?: string,
): string {
  if (unit === "JPY") {
    const absolute = Math.abs(value);
    if (absolute >= 1_000_000_000_000) {
      return `${(value / 1_000_000_000_000).toFixed(2)}兆円`;
    }
    if (absolute >= 100_000_000) {
      return `${Math.round(value / 100_000_000).toLocaleString("ja-JP")}億円`;
    }
    return `${Math.round(value).toLocaleString("ja-JP")}円`;
  }
  if (unit === "USD") {
    const absolute = Math.abs(value);
    const sign = value < 0 ? "-" : "";
    if (absolute >= 1_000_000_000) {
      return `${sign}$${(absolute / 1_000_000_000).toLocaleString("en-US", { maximumFractionDigits: 2 })}B`;
    }
    if (absolute >= 1_000_000) {
      return `${sign}$${(absolute / 1_000_000).toLocaleString("en-US", { maximumFractionDigits: 2 })}M`;
    }
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0,
    }).format(value);
  }
  if (unit === "percent") return `${value.toFixed(1)}%`;
  if (unit === "persons") return `${value.toLocaleString("ja-JP")}名`;
  // 平均年齢と平均勤続年数は同じ unit(years) で入っているため、指標名で単位を分ける
  if (unit === "years") {
    return metricKey === "average_age"
      ? `${value.toFixed(1)}歳`
      : `${value.toFixed(1)}年`;
  }
  return value.toLocaleString("ja-JP");
}

export function latestMetric<
  T extends {
    metric_key: string;
    fiscal_year: string;
    value: string;
    unit: string;
  },
>(
  rows: T[],
  key: string,
): T | undefined {
  return rows
    .filter((row) => row.metric_key === key)
    .sort((a, b) => Number(b.fiscal_year) - Number(a.fiscal_year))[0];
}
