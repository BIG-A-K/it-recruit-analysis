# 企業ページの編集

企業ページは `site/src/pages/companies/<company_id>.mdx` に1社1ファイルで置きます。
MDXはMarkdownの記法にAstroコンポーネントの挿入を加えられる形式です。

## データの役割分担

- `data/*.csv`: 企業横断で比較する数値、識別子、出典などの構造化データ
- `*.mdx`: 企業ページのセクション順、企業固有の解説、見出し、リンク、表などの編集本文
- `site/src/components/company/*.astro`: CSVを読み込んで表示する再利用可能なセクション

CSVの数値を本文へ複写しないでください。数値の更新はCSVだけで行い、MDXには解釈や補足を書きます。

## 加筆例

対象企業のMDXで自由記述用コンポーネントをimportします。

```mdx
import CompanyProse from "../../components/company/CompanyProse.astro";
```

表示したい位置へ、通常のMarkdownを挿入します。

```mdx
<CompanyProse>

## サービス例

セグメントごとの事業内容や具体的なサービスを説明します。

- 箇条書き
- [関連ページへのリンク](https://example.com/)
- Markdownの表

</CompanyProse>

<BusinessSegments companyId={frontmatter.companyId} />
```

`CompanyProse`の開始タグ直後と終了タグ直前には空行を入れます。

## 構造化セクション

| コンポーネント | 表示内容 |
| --- | --- |
| `CompanyOverview` | 社名、分類、基本情報 |
| `CompanyMessage` | 理念・ミッション・企業メッセージ |
| `EmploymentOverview` | 給与、勤続年数、年齢、勤務地 |
| `BusinessSegments` | 最新年度のセグメント別売上・利益。事業説明は直前のMDX本文へ書く |
| `RecruitmentInfo` | レガシー採用情報（既存ページ互換用。新規記事には追加しない） |
| `HealthMetrics` | 流動資産・負債など |
| `FinancialHistory` | 資産状況・IR推移の表 |
| `MetricTrends` | 指標を切り替える推移グラフ |
| `FinancialData` | 上記2つを続けて表示する互換用コンポーネント |
| `CompanySources` | CSVデータが参照する出典 |
| `CompanyProse` | Markdownで書く自由記述 |

コンポーネントはMDX内で並べ替えられ、不要なものは外せます。新しい会社を
`data/companies.csv`へ追加した場合は、同じ`company_id`のMDXも作成します。
`RecruitmentInfo`はレガシーCSV表示用のため、新しい記事では使わず、
採用情報を`CompanyProse`内のMarkdown本文へ記述します。
セグメントの説明は`CompanyProse`へ一度だけ書き、その直後に`BusinessSegments`を置きます。

## データがない企業

コンポーネントは、対象企業に表示できるデータがある場合だけMDXへ記述します。
非上場企業で法定開示の財務・雇用データがない場合、空欄表示のために
`EmploymentOverview`、`BusinessSegments`、`HealthMetrics`、`FinancialHistory`、
`MetricTrends`を置かないでください。

Sakana AIとPreferred Networksでは、採用・事業情報をMarkdown本文で記述し、
利用可能な構造化情報だけを表示しています。

```mdx
<CompanyOverview companyId={frontmatter.companyId} />
<CompanyMessage companyId={frontmatter.companyId} />
<CompanyProse>Markdownの記事本文</CompanyProse>
<CompanySources companyId={frontmatter.companyId} />
```

## 外資系企業と海外開示主体

日本の採用主体と海外の財務開示主体が異なる場合は、両者を別の `company_id` として `companies.csv` へ登録し、`company_relations.csv` で関係を管理します。親会社の財務を日本法人の `company_id` へ複写しません。

日本法人ページで海外開示主体のデータを表示するときは、`BusinessSegments`、`FinancialHistory`、`MetricTrends`、`CompanySources` に開示主体の `company_id` を渡します。直前の `CompanyProse` で、開示主体、連結範囲、原通貨、会計基準、会計年度末と、日本法人単体の数値ではないことを `:::warn` ディレクティブに入れて明記してください。報告セグメントの一部だけを表示するときは、`BusinessSegments` の `showShare={false}` を指定し、不完全な構成比を表示しません。

## 確認

```bash
cd site
npm run build
```

不正な`companyId`、MDX構文エラー、Astroコンポーネントの型エラーはビルド時に検出されます。
