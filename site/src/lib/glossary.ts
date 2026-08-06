const GUIDE_PATH = "/guide/";

// 指標から /guide の解説へ送るための対応表。解説の本文は guide.md が持ち、
// ここでは見出しへのアンカーだけを管理する。guide.md の見出しを変えたらここも直す。
const guideAnchors: Record<string, string> = {
  operating_profit: "営業利益と事業利益",
  business_profit: "営業利益と事業利益",
  operating_cf: "キャッシュフロー",
  investing_cf: "キャッシュフロー",
  financing_cf: "キャッシュフロー",
  net_cf: "キャッシュフロー",
  equity_ratio: "自己資本比率",
  current_assets: "資産状況",
  current_liabilities: "資産状況",
  quick_assets: "当座資産と当座比率",
  // 表示上の計算値。metrics.csv には存在しないキー
  current_ratio: "流動比率",
  quick_ratio: "当座資産と当座比率",
};

export function guideLink(key: string): string | undefined {
  const anchor = guideAnchors[key];
  return anchor ? `${GUIDE_PATH}#${encodeURIComponent(anchor)}` : undefined;
}
