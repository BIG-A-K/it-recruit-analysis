# CSVスキーマ定義

## 表記

CSVには物理的な型がないため、本書では各列の論理型を次のように表す。

| 型 | 形式 |
| --- | --- |
| `string` | UTF-8の文字列 |
| `id` | 小文字の英数字とハイフンからなる文字列 |
| `integer` | 桁区切りのない整数 |
| `decimal` | 桁区切りのない整数または小数 |
| `date` | `YYYY-MM-DD` |
| `year` | 期末年または募集年度を表す4桁の整数 |
| `boolean` | `true` または `false` |
| `url` | `https://` から始まるURL |
| `enum` | 列ごとに定義された値のいずれか |

「必須」はすべての行で値が必要、「条件付き」は行の状態によって必要、「任意」は空欄を許容することを示す。空欄は空文字として保存し、`null`、`N/A`、`-` などの代替文字列は使用しない。

## 共通の列

### `availability`

値の取得状態を表す。

| 値 | 意味 |
| --- | --- |
| `reported` | 出典に値が掲載されている |
| `not_disclosed` | 対象資料では非公表 |
| `not_applicable` | その企業・年度には該当しない |
| `unavailable` | 取得または確認できない |

`reported` の場合は、対象となる値、単位、`source_id` を必須とする。それ以外の場合は値を空欄にし、理由が必要なら `note` に記録する。

### `scope`

値の対象範囲を表す。

| 値 | 意味 |
| --- | --- |
| `consolidated` | 連結グループ |
| `non_consolidated` | 提出会社単体 |
| `<company_id>` | 特定の法人または採用主体 |

## `companies.csv`

企業・法人の基本情報を管理する。

主キー: `company_id`

| 列 | 型 | 必須 | 定義 |
| --- | --- | --- | --- |
| `company_id` | `id` | 必須 | サイト内で不変の企業ID。例: `recruit-holdings` |
| `display_name` | `string` | 必須 | サイトに表示する名称 |
| `name_kana` | `string` | 必須 | `display_name` の読み。ひらがなで記録し、五十音順の並べ替えに使用する |
| `legal_name` | `string` | 必須 | 登記または開示上の正式法人名 |
| `securities_code` | `string` | 任意 | 日本国内の証券コード。先頭ゼロを保持できるよう文字列として扱う |
| `corporate_number` | `string` | 任意 | 国税庁の13桁法人番号 |
| `website_url` | `url` | 任意 | 企業公式サイト |
| `edinet_code` | `string` | 任意 | `E` と5桁の数字からなるEDINETコード |
| `sec_cik` | `string` | 任意 | SECのCIK。10桁にゼロ埋めした数字 |
| `ticker` | `string` | 任意 | 上場市場で使用されるティッカーシンボル |
| `exchange` | `string` | 任意 | ティッカーが上場する取引所 |
| `country_code` | `string` | 任意 | 法人所在国のISO 3166-1 alpha-2国コード |
| `is_active` | `boolean` | 必須 | 現在サイトへ掲載する企業か |

`securities_code` は日本の証券コードだけに使用し、CIK、ティッカーなどの外国識別子を格納しない。`display_name` や `legal_name` が変わっても、既存の `company_id` は変更しない。

## `industries.csv`

サイトで使用する業界分類を管理する。

主キー: `industry_id`

| 列 | 型 | 必須 | 定義 |
| --- | --- | --- | --- |
| `industry_id` | `id` | 必須 | 業界ID。例: `mega-venture` |
| `name` | `string` | 必須 | 表示用の業界名 |
| `description` | `string` | 任意 | 業界の概要 |
| `classification_basis` | `string` | 必須 | この業界に含める判断基準 |
| `is_active` | `boolean` | 必須 | 現在サイトへ掲載する業界か |

## `company_industries.csv`

企業と業界の多対多関係を管理する。企業が複数業界に属する場合は、業界ごとに行を追加する。

主キー: `company_id, industry_id`

| 列 | 型 | 必須 | 定義 |
| --- | --- | --- | --- |
| `company_id` | `id` | 必須 | `companies.csv.company_id` への参照 |
| `industry_id` | `id` | 必須 | `industries.csv.industry_id` への参照 |

## `company_relations.csv`

持株会社、事業会社、採用主体など、企業間の関係を管理する。

主キー: `from_company_id, to_company_id, relation_type, valid_from`

| 列 | 型 | 必須 | 定義 |
| --- | --- | --- | --- |
| `from_company_id` | `id` | 必須 | 関係の起点となる `company_id` |
| `to_company_id` | `id` | 必須 | 関係の終点となる `company_id` |
| `relation_type` | `enum` | 必須 | `parent`、`subsidiary`、`affiliate`、`brand`、`other` |
| `valid_from` | `date` | 必須 | 関係が有効になった日 |
| `valid_to` | `date` | 任意 | 関係が終了した日。継続中は空欄 |
| `source_id` | `id` | 必須 | `sources.csv.source_id` への参照 |
| `note` | `string` | 任意 | 関係の補足 |

関係の向きは `from_company_id` から `to_company_id` とする。例えば子会社から親会社への関係を表す場合は、子会社を `from_company_id`、親会社を `to_company_id`、`relation_type` を `parent` とする。

## `metrics.csv`

給与、人的情報、財務指標を年度別の縦持ち形式で管理する。

主キー: `company_id, metric_key, fiscal_year, scope`

| 列 | 型 | 必須 | 定義 |
| --- | --- | --- | --- |
| `company_id` | `id` | 必須 | `companies.csv.company_id` への参照 |
| `metric_key` | `enum` | 必須 | 指標の種類 |
| `fiscal_year` | `year` | 必須 | 対象期間の期末年 |
| `period_end` | `date` | 必須 | 対象会計期間の期末日 |
| `value` | `decimal` | 条件付き | 指標値。`reported` の場合は必須 |
| `unit` | `string` | 条件付き | `JPY`、`percent`、`years` など |
| `scope` | `enum` または `id` | 必須 | `consolidated`、`non_consolidated`、または対象法人ID |
| `accounting_standard` | `enum` | 任意 | `JGAAP`、`IFRS`、`USGAAP` など |
| `availability` | `enum` | 必須 | 共通の `availability` に従う |
| `source_id` | `id` | 条件付き | `sources.csv.source_id` への参照 |
| `note` | `string` | 任意 | 比較上の注意、XBRL要素ID、コンテキストIDなど |

### 初期の `metric_key`

| 値 | 定義 | 標準単位 | 通常の範囲 |
| --- | --- | --- | --- |
| `average_annual_salary` | 提出会社の平均年間給与 | `JPY` | `non_consolidated` |
| `average_age` | 提出会社従業員の平均年齢 | `years` | `non_consolidated` |
| `average_tenure` | 提出会社従業員の平均勤続年数 | `years` | `non_consolidated` |
| `revenue` | 売上高または売上収益 | `JPY` | `consolidated` |
| `operating_profit` | 営業利益または営業損失 | `JPY` | `consolidated` |
| `business_profit` | 事業利益。IFRS適用会社が営業利益に代えて開示する任意表示利益で、定義が異なるため `operating_profit` と同一視しない | `JPY` | `consolidated` |
| `operating_cf` | 営業活動によるキャッシュ・フロー | `JPY` | `consolidated` |
| `investing_cf` | 投資活動によるキャッシュ・フロー | `JPY` | `consolidated` |
| `financing_cf` | 財務活動によるキャッシュ・フロー | `JPY` | `consolidated` |
| `equity_ratio` | 自己資本比率 | `percent` | `consolidated` |
| `current_assets` | 流動資産 | `JPY` | `consolidated` |
| `current_liabilities` | 流動負債 | `JPY` | `consolidated` |
| `quick_assets` | 当座資産。構成科目を `note` に記録する | `JPY` | `consolidated` |
| `total_funding` | 累計資金調達額。非上場ベンチャーが公式に発表した資金調達の累計。公表値のみ登録し推定値は扱わない | `JPY` | `<company_id>` |
| `employee_count` | 従業員数。連結・単体の別を `scope` と `note` で明示する | `persons` | `consolidated` または `<company_id>` |

新しい指標は、既存キーの意味を変更せず新しい `metric_key` として追加する。企業固有の類似指標を既存キーへ無理に対応させない。

## `segments.csv`

開示資料上の事業セグメントと年度別実績を管理する。

主キー: `company_id, fiscal_year, segment_id`

| 列 | 型 | 必須 | 定義 |
| --- | --- | --- | --- |
| `company_id` | `id` | 必須 | `companies.csv.company_id` への参照 |
| `fiscal_year` | `year` | 必須 | 対象期間の期末年 |
| `segment_id` | `id` | 必須 | 同一企業内で安定したセグメントID |
| `segment_name` | `string` | 必須 | 開示資料上のセグメント名 |
| `description` | `string` | 任意 | セグメントの事業内容 |
| `revenue` | `decimal` | 条件付き | 外部顧客売上高。取得できる場合に記録 |
| `segment_profit` | `decimal` | 条件付き | 開示資料上のセグメント利益 |
| `profit_measure` | `string` | 条件付き | `segment_profit` の定義。例: `営業利益`、`EBITDA+S` |
| `currency` | `string` | 条件付き | ISO 4217通貨コード。例: `JPY` |
| `unit` | `string` | 条件付き | CSVに保存した値の単位。現在は原則 `JPY` |
| `availability` | `enum` | 必須 | 共通の `availability` に従う |
| `source_id` | `id` | 条件付き | `sources.csv.source_id` への参照 |
| `note` | `string` | 任意 | 組替え、名称変更、内部取引などの補足 |

セグメントは企業が開示した区分を保持し、サイト独自の判断で統合しない。`segment_profit` を営業利益と決めつけず、必ず `profit_measure` に資料上の定義を記録する。

## `company_profiles.csv`

企業詳細ページの定型セクションで使用する会社概要と採用情報を管理する。
企業固有の自由記述はMDXへ置き、財務数値は重複保存せず `metrics.csv` と `segments.csv` を使う。

主キー: `company_id`

| 列 | 型 | 必須 | 定義 |
| --- | --- | --- | --- |
| `company_id` | `id` | 必須 | `companies.csv.company_id` への参照 |
| `overview` | `string` | 必須 | 企業と主要事業の概要 |
| `career_url` | `url` | 必須 | 公式の新卒採用情報 |
| `recruitment_summary` | `string` | 必須 | 募集区分や採用方法の要約 |
| `job_categories` | `string` | 必須 | 主な職種を `|` 区切りで列挙 |
| `workplace` | `string` | 必須 | 主な勤務地と配属上の注意 |
| `compensation` | `string` | 必須 | 公式募集要項で確認した初任給・待遇の要約 |
| `employment_note` | `string` | 必須 | 開示主体と採用主体など比較上の注意 |
| `updated_at` | `date` | 必須 | 内容を確認した日 |

## `company_annotations.csv`

企業固有の比較上の注意を、表示対象と結び付けて管理する。取得処理のメモは
`metrics.csv.note` に残し、読者向けの説明だけをこのファイルに記録する。

主キー: `annotation_id`

| 列 | 型 | 必須 | 定義 |
| --- | --- | --- | --- |
| `annotation_id` | `id` | 必須 | 注記を一意に識別するID |
| `company_id` | `id` | 必須 | `companies.csv.company_id` への参照 |
| `section_key` | `enum` | 必須 | 表示セクション。現在は `financials` |
| `target_kind` | `enum` | 必須 | `section`、`metric_group`、`metric` のいずれか |
| `target_key` | `string` | 条件付き | グループ名または `metric_key`。`section` の場合は空欄 |
| `fiscal_year` | `year` | 任意 | 特定年度だけに適用する場合の年度。恒常的な注記は空欄 |
| `text` | `string` | 必須 | 画面に表示する比較上の注意 |
| `source_id` | `id` | 任意 | 根拠資料がある場合の `sources.csv.source_id` への参照 |
| `updated_at` | `date` | 必須 | 内容を確認した日 |

初期の `metric_group` は、`net_cf`、`operating_cf`、`investing_cf`、
`financing_cf` をまとめた `cash_flow` とする。複数の指標に同じ注記を重複して
登録せず、意味のあるグループを追加して対応する。

## `sources.csv`

各データの根拠となる資料を管理する。

主キー: `source_id`

| 列 | 型 | 必須 | 定義 |
| --- | --- | --- | --- |
| `source_id` | `id` | 必須 | 出典を一意に識別するID。EDINETでは原則 `edinet-<document_idの小文字>` |
| `source_type` | `enum` | 必須 | 出典の種類 |
| `title` | `string` | 必須 | 資料またはページの正式名称 |
| `url` | `url` | 必須 | 資料を確認できるURL |
| `document_id` | `string` | 任意 | EDINET書類管理番号など、発行元の文書ID |
| `published_at` | `date` | 任意 | 資料の公開日 |
| `retrieved_at` | `date` | 必須 | データを取得または確認した日 |
| `issuer` | `string` | 必須 | 資料の提出者または発行者 |

### `source_type`

| 値 | 意味 |
| --- | --- |
| `statutory_filing` | EDINETなどの法定開示 |
| `financial_report` | 決算資料、統合報告書、公式IR |
| `recruitment` | 公式採用ページ、募集要項 |
| `corporate` | 企業公式サイト |
| `public_data` | 行政機関などの公開データ |
| `secondary` | 一次情報以外の参考資料 |

## 参照整合性

CSVを更新するときは、少なくとも次を検証する。

- すべての主キーがファイル内で一意である
- `company_id` が `companies.csv` に存在する
- `industry_id` が `industries.csv` に存在する
- 使用中の `source_id` が `sources.csv` に存在する
- `reported` の行に値、単位、出典が存在する
- 数値列を `decimal` として解釈できる
- `period_end` の年と `fiscal_year` の定義が一致する
- 同じ主キーで異なる値が検出された場合は自動採用せず停止する
