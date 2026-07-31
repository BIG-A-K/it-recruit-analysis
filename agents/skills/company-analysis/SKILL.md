---
name: company-analysis
description: 企業の一次情報を一度だけ調査し、比較・集計するIR情報だけをit-recruitのCSVへ構造化し、採用情報・理念・企業固有の説明を企業別MDXへ追加・更新する。主キーupsertとCSV/MDXの責務分離により重複を防ぐ。「企業分析して」「企業データを追加して」「企業記事を書いて」「企業情報を更新して」で使う。
---

# 企業分析

企業情報を調査し、IR情報はCSV、採用情報と編集本文はMDXへ一貫して保存する。ユーザーが片方だけを明示しない限り、IR用CSVまたはMDXだけで終了しない。

## 入力

- 必須: 企業名
- 任意: `focus=就活|投資|両方`。未指定は `両方`
- 任意: `project-root=<path>`。未指定時は、`data/` と `site/src/pages/companies/` を持つ現在のディレクトリ、次に `../it-recruit` を探す
- 任意: `fiscal-year=<年度>`。未指定は取得可能な最新年度を含む3期以上
- 任意: `validate=<command>`。指定時は標準検証に加えて実行する

企業を一意に特定できない場合だけ、候補を示して1問ずつ確認する。

## 必ず読む資料

`project-root` を確定してから、次を読む。

- `docs/data/README.md`: CSVとMDXの正本・責務
- `docs/data/schema.md`: 現行CSVの列、主キー、参照整合性
- `docs/content/companies.md`: MDXの配置とコンポーネント
- [`references/research-checklist.md`](references/research-checklist.md): IRと記事本文の調査項目、検算項目

リポジトリ文書に採用系CSVが定義されていても、このSkillではレガシーデータとして読み取り専用にする。

## データの置き場所

各事実を保存前に次のいずれか一つへ分類する。同じ事実をCSVとMDXの両方へ書かない。

| 内容 | 正本 |
| --- | --- |
| 企業ID、公式URL、業界、開示主体・企業関係 | `companies.csv`、`company_industries.csv`、`company_relations.csv` |
| 有報・決算資料などIR資料の識別情報 | `sources.csv` |
| 有報で開示された給与・人的資本・財務数値 | `metrics.csv` |
| 年度別の報告セグメント名・売上・利益 | `segments.csv` |
| IR数値に対する比較上の注記 | `company_annotations.csv` |
| 理念、会社紹介、採用職種、募集要項、勤務地、待遇、働き方、公式リンク、企業固有の説明 | `site/src/pages/companies/<company_id>.mdx` |

`companies.csv` などのマスタはサイトでIR情報を結合するための最低限の構造であり、採用情報の構造化ではない。

### 更新しないレガシーCSV

- `company_profiles.csv`
- `company_messages.csv`
- `recruitment.csv`
- `segment_descriptions.csv`

このSkillでは上記へ行を追加・更新・削除しない。既存行の一括削除や表示コンポーネントの廃止は別の移行作業として扱う。

## 既存実装の使用

EDINETの取得・正規化・upsertでは、必ずリポジトリ既存のCLIを `project-root` で実行する。EDINET APIの直接呼び出し、場当たり的な取得スクリプト、CSVへの盲目的な追記で代替しない。

### 標準経路

1. `companies.csv` に対象企業の `company_id` があることを確認する。新規企業は先にこのマスタ行を確定する。`edinet_code` が空の企業ではEDINET用CLIを実行せず、「EDINET対象外」と記録して公式IR資料とMDXの処理へ進む。
2. `EDINET_API` が利用できる場合は、原本が取得済みでも次を実行する。`edinet-fetch` は取得済み原本を再ダウンロードせず、`sources.csv`、`metrics.csv`、`segments.csv` を主キーでupsertする。

   ```bash
   uv run --env-file .env edinet-fetch <company_id> \
     --start <YYYY-MM-DD> \
     --end <YYYY-MM-DD>
   ```

3. 検索期間は次の規則だけで決める。
   - ユーザーが期間を指定した場合: その期間を使う。
   - `fiscal-year=YYYY` の場合: `YYYY-01-01` から `(YYYY+1)-06-30` までとし、終了日が未来なら実行日を使う。
   - どちらも未指定の場合: 実行日の400日前から実行日までとする。
   - 対象書類が見つからない場合: 勝手に期間を変えたり手入力へ切り替えたりせず、使用した期間と不足情報を報告する。
4. 通常は最新の有価証券報告書だけを処理し、`--all` はユーザーが期間内の全書類を明示した場合だけ使う。
5. APIを使わず取得済み原本を再変換する場合だけ、原本ディレクトリと対応する `sources.csv` 行の存在を確認して次を使う。

   ```bash
   uv run edinet-normalize <company_id> <doc_id> \
     --period-end <YYYY-MM-DD>
   ```

### 例外処理

- CLIが対応する指標とセグメントは、手作業で `metrics.csv` や `segments.csv` へ書かない。
- EDINET原本に必要なXBRL要素があるのにCLIが未対応なら、`src/it_recruit_data/normalize.py` の共通ルールとテストを拡張し、CLIを再実行する。企業ごとの一回限りの変換コードを作らない。
- EDINETにない公式IR資料だけを補完する場合は、現行スキーマの主キーで `sources.csv` を先にupsertし、その `source_id` を使ってIR行をupsertする。根拠がない値は追加しない。
- CLIが失敗した場合は原因を診断し、修正または失敗理由の報告を行う。黙って手編集へ切り替えない。
- CLI実行後は対象企業の `metrics.csv`、`segments.csv`、`sources.csv` の差分を確認してからMDXへ進む。

## ワークフロー

1. **変更範囲を確認する。** Gitの未コミット変更を確認し、ユーザーの変更を上書きしない。対象企業のIR行、必要なマスタ行、企業MDX以外を変更対象にしない。
2. **既存状態を棚卸しする。** IR用CSVから対象企業のID、主キー、年度、出典、業界、企業関係を確認し、同名・旧社名・ブランド・同一URL・証券コード・法人番号による重複候補を探す。同じ企業を扱うMDXと、移行元に使える `yukijya_doh` の既存記事も確認する。
3. **企業境界とIDを確定する。** 採用主体、上場・開示主体、連結範囲、基準日、会計年度、会計基準、通貨、単位を固定する。既存企業は既存 `company_id` を再利用し、社名変更や表記差で新IDを作らない。
4. **調査台帳を一度だけ作る。** 各事実へ `ir_csv` または `mdx` の保存先、対象、時点、単位、出典を付ける。IRは法定開示と決算資料を優先し、採用情報は公式採用サイトを確認する。旧記事は下書きとして利用できるが、変動する採用情報を現在の公式情報で再確認する。
5. **既存CLIでIRを更新する。** 「既存実装の使用」に従って `edinet-fetch` または条件を満たす場合だけ `edinet-normalize` を実行する。IR数値を支える資料だけを `sources.csv` へ保存し、MDXだけで使う採用ページは本文へ直接リンクする。
6. **非EDINET情報だけを補完する。** CLIの差分を確認し、EDINETにない公式IR資料と `company_annotations.csv` だけを現行スキーマの主キーで補完する。CLI対応項目を手入力で上書きせず、対象外の行、未知の列、既存の並びを壊さない。
7. **MDXを作成または更新する。** パスを `site/src/pages/companies/<company_id>.mdx` に固定する。理念、企業紹介、採用情報、公式リンクは `CompanyProse` 内へMarkdownで書き、該当箇所の近くに公式URLと確認時点を置く。IR数値やセグメント表は本文へ転記せず、対応するAstroコンポーネントで表示する。
8. **重複を横断確認する。** IR用CSVの主キー、`company_id`、`source_id`、対象企業のMDXパスが一意か確認する。MDXにIR数値・年度別セグメント表を複写していないこと、今回の採用情報をレガシーCSVへ書いていないことを確認する。サイトで算出する `net_cf` などの派生値をCSVへ保存しない。
9. **検算・検証する。** IR値の年度、単位、符号、連結・単体、会計基準を確認し、比率を元数値から再計算する。採用情報の対象年度・採用主体・確認日を確認する。`uv run pytest` と `npm --prefix site run build` を実行し、`validate` があれば追加実行する。

## MDXの構成

- 全企業: `CompanyOverview` と `CompanyProse`
- IRデータがある場合だけ: `EmploymentOverview`、`BusinessSegments`、`HealthMetrics`、`FinancialHistory`、`MetricTrends` または互換用の `FinancialData`、`CompanySources`
- `CompanyProse` 内: 理念・会社紹介・公式サイト・採用情報・企業固有の補足

新しいMDXへ `CompanyMessage` と `RecruitmentInfo` を追加しない。これらはレガシーCSVを表示する既存ページとの互換用とする。既存ページを更新する場合も、ユーザーが移行を求めない限りページ全体を機械的に書き換えない。

## ルール

- CSVへ構造化する内容を、IR資料から取得した比較・集計対象と最低限の結合用マスタに限定する。
- 有報に掲載された平均年間給与、平均年齢、平均勤続年数、従業員数などはIR情報として `metrics.csv` に保存する。
- 採用サイトの職種、応募資格、初任給、勤務地、働き方、選考情報はMDXだけへ保存する。
- CSVへ企業ごとの別ファイルを作らず、同じ主キーを盲目的にappendしない。
- EDINETの取得・正規化・upsertを既存CLI以外で再実装しない。
- 最新採用情報と過去のIR情報を同じ時点の事実として扱わない。
- 検索結果のスニペット、記憶、概算を根拠にしない。
- IRの欠損値はスキーマの `availability` で表し、数値列へ説明文字列を入れない。
- 評価、応募判断、投資判断をCSVへ保存せず、MDXにも根拠のない評価や推測を書かない。
- 企業、業界、IR出典を削除せず、削除やID変更が必要ならユーザーへ確認する。
- `yukijya_doh/src/content/recruit/` へ同じ記事を同時生成しない。

## 出力

- 更新したIR用CSVとMDXのパス
- 実行した既存CLIと引数
- 追加・更新したIR年度と各CSVの行数
- MDXへ記録した採用情報の対象年度・確認日
- 再利用した既存IDと、重複追加を避けた対象
- 更新しなかったレガシーCSV
- 使用した主要資料、欠損項目、検算、テスト、ビルドの結果
