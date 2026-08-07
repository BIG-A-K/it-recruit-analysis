import { fxRates, type FxRate, type Metric } from "./data";

// 会計基準（IAS 21、ASC 830）に合わせ、貸借対照表項目は決算日の相場、
// 損益・キャッシュフローなどの期間項目は対象期間の平均相場で換算する。
const balanceSheetKeys = new Set([
  "current_assets",
  "current_liabilities",
  "quick_assets",
]);

// 通貨建ての単位。これ以外（percent・persons・years など）は換算せずそのまま比較できる。
const currencyUnits = new Set(["JPY", "USD"]);

const displayCurrency = "JPY";

export type MetricWithFx = Metric & {
  // 会計基準や通貨をまたいで横並びするときに使う値。換算できなかった場合は空文字。
  comparable_value: string;
  comparable_unit: string;
  fx_rate?: string;
  fx_rate_type?: string;
  fx_rate_id?: string;
  fx_source_id?: string;
};

function rateTypeFor(metricKey: string): FxRate["rate_type"] {
  return balanceSheetKeys.has(metricKey) ? "closing" : "average";
}

function findRate(metric: Metric): FxRate | undefined {
  const rateType = rateTypeFor(metric.metric_key);
  return fxRates.find(
    (rate) =>
      rate.base_currency === metric.unit &&
      rate.quote_currency === displayCurrency &&
      rate.rate_type === rateType &&
      rate.period_end === metric.period_end,
  );
}

// 外貨建ての指標に円換算値を添える。換算値は metrics.csv には保存せず、
// ネットCFや流動比率と同じくサイト側の算出値として扱う。
export function withJpyEquivalent(rows: Metric[]): MetricWithFx[] {
  return rows.map((row) => {
    if (!currencyUnits.has(row.unit) || row.unit === displayCurrency) {
      return { ...row, comparable_value: row.value, comparable_unit: row.unit };
    }

    const rate = findRate(row);
    // 相場を用意していない年度は横並びの対象から外す。推定値で埋めない。
    if (!rate) {
      return { ...row, comparable_value: "", comparable_unit: displayCurrency };
    }

    return {
      ...row,
      comparable_value: String(Number(row.value) * Number(rate.rate)),
      comparable_unit: displayCurrency,
      fx_rate: rate.rate,
      fx_rate_type: rate.rate_type,
      fx_rate_id: rate.rate_id,
      fx_source_id: rate.source_id,
    };
  });
}
