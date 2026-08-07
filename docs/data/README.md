# データ管理方針

## 基本方針

企業横断で比較する構造化データは、`data/` 直下の用途別CSVを正本として管理する。
企業詳細ページの構成と企業固有の自由記述は、`site/src/pages/companies/<company_id>.mdx`で管理する。
MDXの編集方法は[企業ページの編集](../content/companies.md)を参照する。

企業ごとのCSVには分割せず、各CSVに全企業のデータを格納する。企業は `company_id`、業界は `industry_id`、出典は `source_id` で識別し、CSV間をこれらのIDで関連付ける。

初版の対象企業数では、全結合CSVの方が次の点で管理しやすい。

- 企業横断比較や業界統計にそのまま利用できる
- 企業ごとに同じ構造のファイルを増やさずに済む
- スキーマ変更を一度に反映できる
- Astroのビルド時に企業別ファイルを結合する処理が不要になる

## ディレクトリ構成

```text
data/
├── companies.csv
├── industries.csv
├── company_industries.csv
├── company_relations.csv
├── metrics.csv
├── segments.csv
├── sources.csv
└── raw/
    ├── edinet/
    │   └── <document_id>/
    └── sec/
        └── <CIK>/
            └── <accession-number>/
```

`data/*.csv` はGitで管理する。`data/raw/` は外部サービスから再取得できる原本の保存場所とし、Gitでは管理しない。

## CSVの役割

各列の型、必須条件、許容値、外部キーは
[CSVスキーマ定義](schema.md)に定義する。

| ファイル | 内容 | 主キー |
| --- | --- | --- |
| `companies.csv` | 企業・法人の基本情報 | `company_id` |
| `industries.csv` | サイトで使用する業界分類 | `industry_id` |
| `company_industries.csv` | 企業と業界の多対多関係 | `company_id, industry_id` |
| `company_relations.csv` | 持株会社、事業会社、関連会社などの関係 | `from_company_id, to_company_id, relation_type, valid_from` |
| `metrics.csv` | 給与、人的情報、財務指標の年度別データ | `company_id, metric_key, fiscal_year, scope` |
| `segments.csv` | 事業セグメントの年度別実績 | `company_id, fiscal_year, segment_id` |
| `sources.csv` | EDINET、公式IR、採用サイトなどの出典 | `source_id` |
| `fx_rates.csv` | 外貨建て指標を円換算して表示するための為替相場 | `rate_id` |

## 共通ルール

- CSVはUTF-8、ヘッダー付きで保存する
- 列名は `snake_case`、企業や業界のIDは `kebab-case` とする
- 日付は `YYYY-MM-DD`、会計年度は期末年の4桁で記録する
- 数値列に桁区切り、通貨記号、単位文字列を含めない
- 金額や比率の単位は専用の列で明示する
- 連結、単体、対象法人の違いは `scope` で区別する
- 日本基準、IFRSなどの違いは `accounting_standard` に記録する
- 複数の値を1セルに詰め込まず、行を分ける
- 同じ主キーの行を追加せず、既存行を更新する
- 表示名ではなく、変更されにくいIDをCSV間の参照に使用する

## 欠損値

取得できない値を `0` として保存しない。値の列は空欄にし、`availability` で状態を区別する。

| 値 | 意味 |
| --- | --- |
| `reported` | 出典に値が掲載されている |
| `not_disclosed` | 対象資料では非公表 |
| `not_applicable` | その企業・年度には該当しない |
| `unavailable` | 取得または確認できない |

`reported` の行には、値、単位、`source_id` を必須とする。

## 出典管理

指標や採用情報の各行は `source_id` を通じて `sources.csv` の出典に関連付ける。

EDINETまたはSECの法定開示から取得したデータでは、以下を保持する。

- EDINET書類管理番号またはSEC accession number
- 書類名
- 提出者
- 公開日
- 取得日
- API上の文書URL

EDINETやSECの法定開示で取得できない項目は、企業の公式IR、公式採用サイト、公式サイトなどの一次情報で補完する。SEC原本は `data/raw/sec/<CIK>/<accession-number>/` に保存する。一次情報を確認できない場合に限り、二次情報を参考情報として使用する。

## 更新手順

```mermaid
flowchart LR
    A["EDINET・公式サイトから取得"]
    B["原本をdata/rawへ保存"]
    C["用途別CSVへ変換・追記"]
    D["主キー・参照・値を検証"]
    E["変更内容を確認"]
    F["Astroでサイトをビルド"]

    A --> B
    B --> C
    C --> D
    D --> E
    E --> F
```

1. `company_id` と対象法人を確認する
2. 資料を取得し、出典を `sources.csv` に登録する
3. 指標、セグメント、採用情報を対応するCSVへ変換する
4. 主キーの重複、存在しない企業ID・出典IDへの参照、数値と単位を検証する
5. 前年度値や原本と照合し、不自然な桁・符号・対象範囲がないか確認する
6. 検証済みのCSVを使ってサイトをビルドする

取得・変換処理は同じ文書を再実行できるようにし、同じ主キーのデータは追加ではなく更新する。同じ主キーに異なる値が見つかった場合は、自動的に一方を採用せず処理を停止して確認する。

## CSVの書き込みは csv-upsert を使う

`data/` 配下のCSVをエディタやAIエージェントがテキストとして直接編集すると、改行コード混在・列ズレ・クォート漏れによるパースエラーが起きる（過去に CRLF/LF 混在でサイトのビルドが停止した）。**手動での行追加・更新はすべて `csv-upsert` CLI を経由する。** EDINET・SECの正規化は従来どおり `edinet-normalize` / `sec-normalize` が同じ書き込み経路を使う。

```bash
# JSON Lines（1行1オブジェクト）を標準入力で渡す
uv run csv-upsert sources <<'EOF'
{"source_id": "edinet-s100xxxx", "source_type": "edinet", "title": "有価証券報告書", "url": "https://...", "document_id": "S100XXXX", "published_at": "2026-06-30", "retrieved_at": "2026-08-05", "issuer": "株式会社Example"}
EOF

uv run csv-upsert metrics <<'EOF'
{"company_id": "example", "metric_key": "revenue", "fiscal_year": "2026", "period_end": "2026-03-31", "value": "1000000000", "unit": "JPY", "scope": "consolidated", "accounting_standard": "IFRS", "availability": "reported", "source_id": "edinet-s100xxxx"}
EOF
```

対象テーブル: `companies` / `industries` / `company_industries` / `company_relations` / `metrics` / `segments` / `sources` / `company_annotations`（`company_profiles` はレガシーのため対象外）。

CLIの挙動:

- 主キー（[schema.md](schema.md) と同一定義）が一致する既存行は、渡したフィールドだけを更新する（部分更新可）。一致しなければ追加する
- 書き込み前に検証し、1件でもエラーがあれば**何も書き込まずに**終了する
  - 未知のフィールド名（列名のtypo）
  - 主キーフィールドの欠落・空値
  - `companies.csv` に存在しない `company_id` への参照
  - `sources.csv` に存在しない `source_id` への参照（出典を先に登録する）
  - 入力内の主キー重複
- 改行コードLF・最小クォートで全体を書き直すため、表記が常に一定に保たれる
- 実行結果として `N added, N updated, N unchanged` を報告する（worker結果契約の `artifacts` にそのまま使える）
- JSON配列（`[{...}, {...}]`）の入力も受け付ける

値の妥当性（`availability` の値域、単位、桁など）はCLIでは検証しない。`uv run pytest tests/test_data_integrity.py` で確認する。

## 企業別分割を検討する条件

当面は全結合CSVを維持する。次の問題が実際に発生した場合に、`data/companies/<company_id>/` への分割やデータベースへの移行を検討する。

- 企業数の増加によりCSVの確認や処理が明確に遅くなった
- 複数人の同時編集による競合が頻発する
- 企業単位の更新・公開・権限管理が必要になった
- CSVの検証や結合処理が運用上の負担になった

分割する場合も、サイトが参照するデータ構造と主キーは維持し、企業横断比較用の全結合データをビルド時に生成する。
