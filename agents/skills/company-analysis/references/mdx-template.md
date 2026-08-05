# 企業MDXテンプレート

`site/src/pages/companies/<company_id>.mdx` の構成。新規作成と既存記事の更新の両方でこれを満たす。

## セクション順

`CompanyProse` とAstroコンポーネントを**交互に配置**する。proseを1ブロックに固め、コンポーネントを末尾へまとめない。

```mdx
---
layout: ../../layouts/CompanyLayout.astro
companyId: <company_id>
---

import CompanyOverview from "../../components/company/CompanyOverview.astro";
import CompanyProse from "../../components/company/CompanyProse.astro";
import EmploymentOverview from "../../components/company/EmploymentOverview.astro";
import BusinessSegments from "../../components/company/BusinessSegments.astro";
import HealthMetrics from "../../components/company/HealthMetrics.astro";
import FinancialHistory from "../../components/company/FinancialHistory.astro";
import MetricTrends from "../../components/company/MetricTrends.astro";
import CompanySources from "../../components/company/CompanySources.astro";

<CompanyOverview companyId={frontmatter.companyId} />

<CompanyProse>

<!-- 企業理念と会社紹介（本文） -->

## サイト
<!-- 公式リンクのツリー -->

</CompanyProse>

<EmploymentOverview companyId={frontmatter.companyId} />

<CompanyProse>

## 採用情報
### 新卒
<!-- 採用主体・確認日・職種別の募集要項表 -->

## サービス例
<!-- セグメント別のサービス表 -->

</CompanyProse>

<BusinessSegments companyId={frontmatter.companyId} />

<CompanyProse>

## 関連企業
<!-- 親会社・主な子会社の表 -->

</CompanyProse>

<HealthMetrics companyId={frontmatter.companyId} />

<FinancialHistory companyId={frontmatter.companyId} />

<MetricTrends companyId={frontmatter.companyId} />

<CompanySources companyId={frontmatter.companyId} />
```

このセクション順以外の見出しを足さない。
`originalPublishedAt: YYYY/MM/DD` は `yukijya_doh` から移行した記事にだけ付ける。

## 各要素の要件

| 要素 | 担当 | 満たす内容 |
| --- | --- | --- |
| 企業理念 | 本文 | ミッション・ビジョン・スローガンを公式表記のまま引用し、設立経緯と規模を含む会社紹介を2〜3文。引用元URLと確認日を近くに置く |
| サイトリンク | 本文 `## サイト` | HP、IR、有価証券報告書（**取得した全年度のPDF**）、採用情報、新卒採用をネストした箇条書きで示す |
| 採用情報・新卒情報 | 本文 `## 採用情報` / `### 新卒` | 採用主体、確認日、職種ごとの勤務地・初任給・固定残業・標準年収の表、選考区分、賞与や超過手当の注記 |
| 事業説明 | 本文 `## サービス例` | 報告セグメントごとの事業内容・具体的サービス名を表にし、`BusinessSegments` の直前に置く |
| セグメント別売上 | `BusinessSegments` | `segments.csv` の最新年度の売上・利益だけを表示し、事業説明を重複させない |
| 関連企業 | 本文 `## 関連企業` | 親会社・主な子会社を具体名で。事業内容と対応する報告セグメントを併記 |
| 健全性指標 | `HealthMetrics` | `current_assets`、`current_liabilities`、`quick_assets` を最新期以上 |
| 資産状況 | `FinancialHistory` | 売上・利益・CF・自己資本比率を3期以上 |
| 棒グラフ | `MetricTrends` | 下記の全キーを登録し、切り替え時に空のグラフが出ないようにする |
| 出典 | `CompanySources` | — |

`FinancialData` は互換用。新規記事では `FinancialHistory` と `MetricTrends` を分けて置く。

## 棒グラフを埋める指標

`MetricTrends` は `site/src/lib/company-financials.ts` の `financialMetricKeys` を切り替えて描画する。

| `metric_key` | 期数の目安 |
| --- | --- |
| `revenue` | 3期以上 |
| `operating_profit` | 3期以上 |
| `operating_cf` | 3期以上 |
| `investing_cf` | 3期以上 |
| `financing_cf` | 3期以上 |
| `equity_ratio` | 3期以上 |
| `current_assets` | 最新期以上 |
| `current_liabilities` | 最新期以上 |
| `quick_assets` | 最新期以上 |

`net_cf` はサイトが3区分から算出する派生値なので `metrics.csv` へ保存しない。
`quick_assets` は算定に含めた科目を `note` に記録する。開示がなく取得できないキーは `availability` で欠損を表し、数値を推定しない。

## 書式

**表と見出し・ディレクティブの間には必ず空行を入れる。** 空行がないと見出しが表に飲まれる。

新卒の募集要項は職種を行にした表にする。職種名は募集ページへリンクする。
**注記を付ける列には `※n` を列名に書き、`:::info` の定義と対応させる。** 定義だけを置いて表側に参照がない状態にしない。

```markdown
| 職種 | 勤務地 | 基準給与（月） | 基礎給（月） | 固定時間外手当（月）※1 | 標準年収※2 |
| --- | --- | --- | --- | --- | --- |
| [エンジニア](https://example.com/recruit/newgrads/engineer/) | 東京・大阪 | 336,000 円〜 | 259,616 円〜 | 76,384 円〜 | 5,040,000 円〜 |

:::info
※1 月 35 時間を超過した場合、別途超過時間分の手当を支給<br />※2 賞与を含む 15 か月換算。年間を通じて標準的な評価だった場合の金額
:::
```

標準年収が月給の12か月分と一致しないときは、**何か月換算かを注記に書く。**
勤務地が全職種共通なら表の近くに適用範囲とともに書き、職種ごとの勤務地欄を同じ文言で埋めない。

但し書き・補足は `:::info`、読者の判断に影響する注意（開示主体と採用主体の違い、会計基準・通貨・連結範囲の差、単純比較できない条件）は `:::warn` に入れる。通常の段落や `####` 見出しで済ませない。
利用できるディレクティブは `info`、`warning`、`danger` とその別名（`site/src/lib/remark-admonition.mjs`）。未対応名はビルド時に警告になる。

`## サービス例` はセグメント区分を行にし、サービス名を列挙する。直後に `BusinessSegments` を置き、その後に `## 関連企業` を置く。過年度資料に基づく記述には、資料の年度と、終了・改称したサービスの注記を `:::info` で添える。
中身のないセル（`| その他 | その他 |`）を残さない。

## 情報が足りないとき

- 公式採用ページに待遇の記載がない: 表を作らず、確認できた職種区分と選考区分を文章で書き、募集要項の所在（各職種ページ末尾など）を示す。仮の数値を置かない。
- セグメント開示がない非上場企業: `EmploymentOverview`、`BusinessSegments`、`HealthMetrics`、`FinancialHistory`、`MetricTrends` を置かず、事業説明を本文へ書く。
- 親会社・子会社がない: `## 関連企業` を見出しごと省く。空の表を残さない。
