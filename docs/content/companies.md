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
<BusinessSegments companyId={frontmatter.companyId} />

<CompanyProse>

## この会社を見るときのポイント

ここには企業固有の解説を自由に書けます。

- 箇条書き
- [関連ページへのリンク](https://example.com/)
- Markdownの表

</CompanyProse>
```

`CompanyProse`の開始タグ直後と終了タグ直前には空行を入れます。

## 構造化セクション

| コンポーネント | 表示内容 |
| --- | --- |
| `CompanyOverview` | 社名、分類、基本情報 |
| `CompanyMessage` | 理念・ミッション・企業メッセージ |
| `EmploymentOverview` | 給与、勤続年数、年齢、勤務地 |
| `BusinessSegments` | 事業概要、事業セグメント |
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

## データがない企業

コンポーネントは、対象企業に表示できるデータがある場合だけMDXへ記述します。
非上場企業で法定開示の財務・雇用データがない場合、空欄表示のために
`EmploymentOverview`、`HealthMetrics`、`FinancialHistory`、
`MetricTrends`を置かないでください。

Sakana AIとPreferred Networksでは、採用・事業情報をMarkdown本文で記述し、
利用可能な構造化情報だけを表示しています。

```mdx
<CompanyOverview companyId={frontmatter.companyId} />
<CompanyMessage companyId={frontmatter.companyId} />
<CompanyProse>Markdownの記事本文</CompanyProse>
<CompanySources companyId={frontmatter.companyId} />
```

## 確認

```bash
cd site
npm run build
```

不正な`companyId`、MDX構文エラー、Astroコンポーネントの型エラーはビルド時に検出されます。
