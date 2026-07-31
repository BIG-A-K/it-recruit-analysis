# 企業データCSVスキーマ

CSVはUTF-8、ヘッダー付き、RFC 4180互換で保存する。IDと列名には小文字のsnake_caseを使用する。

## 共通ルール

- 日付は `YYYY-MM-DD`、会計年度は期末年の4桁で記録する。
- 数値列には桁区切り、通貨記号、単位文字列を含めない。
- 金額の単位は行の `unit` で明示する。
- 欠損値の `value` は空欄にし、`availability` を必ず設定する。
- `availability` は `reported`、`not_disclosed`、`not_applicable`、`unavailable` のいずれかとする。
- 複数値を1セルへ詰め込まず、行を分ける。
- ファイルに既存の追加列がある場合は削除しない。

## `companies.csv`

企業・法人の基本情報を管理する。

```csv
company_id,display_name,legal_name,securities_code,corporate_number,website_url,edinet_code,is_active
```

- 主キー: `company_id`
- `company_id`: 公式ドメインを基にした安定したkebab-case
- `is_active`: `true` または `false`

## `industries.csv`

サイト独自の業界分類を管理する。

```csv
industry_id,name,description,classification_basis,is_active
```

- 主キー: `industry_id`
- `classification_basis`: その業界へ分類する条件

## `company_industries.csv`

企業と業界の多対多関係を管理する。

```csv
company_id,industry_id
```

- 複合主キー: `company_id,industry_id`
- `company_id` と `industry_id` は対応するマスタに存在すること

## `company_relations.csv`

親会社、子会社、関連会社などの企業間関係を管理する。

```csv
from_company_id,to_company_id,relation_type,valid_from,valid_to,source_id,note
```

- 複合主キー: `from_company_id,to_company_id,relation_type,valid_from`
- `relation_type`: `parent`、`subsidiary`、`affiliate`、`brand`、`other`
- 関係の向きは `from_company_id` から `to_company_id` とする

## `metrics.csv`

給与・人的資本・財務指標の年度別データを縦持ちで管理する。

```csv
company_id,metric_key,fiscal_year,period_end,value,unit,scope,accounting_standard,availability,source_id,note
```

- 複合主キー: `company_id,metric_key,fiscal_year,scope`
- `scope`: `consolidated`、`non_consolidated`、または対象法人ID
- `metric_key` の初期必須値:
  - `average_annual_salary`
  - `average_age`
  - `average_tenure`
  - `revenue`
  - `operating_profit`
  - `operating_cf`
  - `investing_cf`
  - `financing_cf`
  - `equity_ratio`
- `availability=reported` の場合は `value`、`unit`、`source_id` を必須とする

## `segments.csv`

事業セグメントと年度別実績を管理する。

```csv
company_id,fiscal_year,segment_id,segment_name,description,revenue,segment_profit,profit_measure,currency,unit,availability,source_id,note
```

- 複合主キー: `company_id,fiscal_year,segment_id`
- 開示上のセグメント名と区分を保ち、独自に統合しない
- `profit_measure`: 営業利益、調整後EBITDAなど、開示資料上の利益指標名

## `recruitment.csv`

採用職種、勤務地、初任給、労働条件などを縦持ちで管理する。

```csv
company_id,recruitment_year,fact_key,item_id,value,unit,scope,availability,source_id,note
```

- 複合主キー: `company_id,recruitment_year,fact_key,item_id`
- `item_id`: 同じ項目が複数ある場合に区別する安定したID
- `fact_key` の例:
  - `job_title`
  - `job_description`
  - `work_location`
  - `starting_salary`
  - `overtime_hours`
  - `paid_leave_usage`
  - `parental_leave_rate`
- 募集年度と財務年度を混同しない

## `sources.csv`

値の根拠となる資料を管理する。

```csv
source_id,source_type,title,url,document_id,published_at,retrieved_at,issuer
```

- 主キー: `source_id`
- `source_type`: `statutory_filing`、`financial_report`、`recruitment`、`corporate`、`public_data`、`secondary`
- EDINET書類は `document_id` に書類管理番号を記録する

## 任意項目

新しい指標や採用項目を追加するときは、既存キーの意味を変更せず、新しい `metric_key` または `fact_key` を追加する。既存ファイルの責務に収まらないデータは、用途と主キーを定義した専用CSVへ分離する。
