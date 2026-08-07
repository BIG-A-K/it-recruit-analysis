export const metricLabels: Record<string, string> = {
  average_annual_salary: "平均年間給与",
  net_cf: "ネットCF",
  // 働き方に関する指標。給与のつぎに気になる項目として、財務指標より前に並べる
  gender_pay_gap: "男女の賃金の差異",
  female_manager_ratio: "女性管理職比率",
  // 男性育休の取得率は、育児休業だけで算定する会社と育児目的休暇を含めて算定する
  // 会社が混在し、後者のほうが高く出る。算定範囲を混ぜて順位を付けると範囲の違いを
  // そのまま優劣として読ませてしまうため、指標名にどちらの範囲かを書いて選択肢を分ける。
  male_childcare_leave_rate: "男性育休取得率（育児目的休暇を含まない）",
  male_childcare_leave_rate_with_leave: "男性育休取得率（育児目的休暇を含む）",
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
  rd_expenses: "研究開発費",
};

export const metricDisplayOrder = Object.keys(metricLabels);

// 選んだときだけ添える、その指標の読み方の注意書き
export const metricNotes: Record<string, string> = {
  male_childcare_leave_rate:
    "育児休業の取得だけで算定した公表値です。育児目的休暇を含めて算定した値とは対象範囲が違うため、同じ図には並べていません。",
  male_childcare_leave_rate_with_leave:
    "育児目的休暇を含めて算定した公表値です。育児休業だけで算定した値より高く出るため、そちらとは同じ図に並べていません。",
};

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

// scope を指定すると連結・単体を絞り込む。従業員数のように同じ指標を
// 連結と単体の両方で持つ場合、指定しないと年度の新しいほうが選ばれる。
export function latestMetric<
  T extends {
    metric_key: string;
    fiscal_year: string;
    value: string;
    unit: string;
    scope?: string;
  },
>(
  rows: T[],
  key: string,
  scope?: string,
): T | undefined {
  return rows
    .filter(
      (row) =>
        row.metric_key === key && (scope === undefined || row.scope === scope),
    )
    .sort((a, b) => Number(b.fiscal_year) - Number(a.fiscal_year))[0];
}
