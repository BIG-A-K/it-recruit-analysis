---
name: company-analysis
description: 企業のIR情報を法定開示から収集してCSVへ、理念・採用情報・事業説明をMDX記事へ書き分ける分析全体を統括する。調査台帳 ledger/<company_id>.yaml を作成し、IR・採用・企業事業調査をSubAgentで並列実行してから記事化する。中断した企業は台帳から再開する。「企業分析して」「企業データを追加して」「企業記事を書いて」「〜の続きから」で使う。
argument-hint: "企業名 [focus=就活|投資|両方] [fiscal-year=YYYY] [project-root=<path>] [validate=<command>]"
---

# 企業分析（統括）

企業を1社調べ、**IR数値はCSV**、**記事本文はMDX**という2つの正本へ書き分ける。
進行状態と調査結果は調査台帳 `ledger/<company_id>.yaml`（[references/ledger.md](references/ledger.md)）へ永続化し、フェーズ単位で中断・再開できるようにする。
ユーザーが片方だけを指定しない限り、どちらか一方で終わらせない。

## 入力

| 引数 | 未指定時 |
| --- | --- |
| 企業名（必須） | — |
| `focus=就活｜投資｜両方` | 両方 |
| `project-root=<path>` | `data/` と `site/src/pages/companies/` を持つ現在地、次に `../it-recruit` |
| `fiscal-year=<年度>` | 取得可能な最新年度を含む3期以上 |
| `validate=<command>` | 標準検証のみ |

企業を一意に特定できないときだけ、候補を挙げて確認する。

## フェーズと担当スキル

| フェーズ | 担当 | 台帳の `phases` |
| --- | --- | --- |
| 準備・台帳作成 | このスキル | — |
| IRデータ（CSV） | `company-ir-worker`（`company-ir mode=worker`） | `ir` |
| 新卒募集要項 | `company-recruit-worker`（`company-research scope=recruit mode=worker`） | `recruit` |
| 企業・事業・記事材料 | `company-profile-worker`（`company-research scope=segments mode=worker`） | `segments` / `article` の調査行 |
| worker結果の統合 | このスキル | `ir` / `recruit` / `segments` |
| 記事（MDX）・検証 | `company-article` | `article` / `verify` |

準備後の依存関係は次のDAGとする。並列対象のworkerは1つずつ待たず、**同じメッセージでTaskを複数呼び出して同時起動する。**

```text
準備・企業境界確定
  ├─ company-ir-worker ─────────────┐
  ├─ company-recruit-worker ────────┼─ 統括agentが台帳へ統合 ─ company-article
  └─ company-profile-worker ────────┘
```

各workerの完了条件を満たすまで `company-article` へ進まない。MDXを先に作って、後から調査結果で埋める進め方はしない。

### Writer境界

| 出力 | writer |
| --- | --- |
| `sources.csv` / `metrics.csv` / `segments.csv` | `company-ir-worker` |
| workerの調査結果 | 各workerの最終YAML |
| `ledger/<company_id>.yaml` | この統括agentだけ |
| 企業MDX | `company-article`だけ |

worker同士で同じファイルを編集させない。詳細は [worker結果契約](references/worker-contract.md) に従う。

## 3つの原則

以降のすべての判断はこの3つに帰着する。担当スキルにも適用される。

### 原則1: 正本を分ける

比較・集計する数値はCSV、読み物はMDX。**同じ事実を両方へ書かない。** 内容ごとの正本は [references/ledger.md](references/ledger.md) の保存先定義に従う。
`company_profiles.csv` は**レガシー**。読むだけで、行を追加・更新・削除しない。

### 原則2: 既存CLIを優先し、失敗時だけクロールする

法定開示の取得・正規化・upsertは、リポジトリのCLI（`edinet-fetch` / `edinet-normalize` / `sec-fetch` / `sec-normalize`）で行う。手順の詳細は `company-ir` が持つ。**企業ごとの一回限りの取得・変換コードを書かない。**

### 原則3: 採用主体と開示主体を分ける

日本で採用する法人と、財務を開示する法人は別の `company_id` を持つ。
親会社の数値を日本法人の `company_id` へ複写しない。外資系企業の詳しい扱いは [references/foreign-companies.md](references/foreign-companies.md)。

## 事前に読む資料

`project-root` を確定してから読む。

- `docs/data/README.md` — CSVとMDXの責務
- `docs/data/schema.md` — 列・主キー・参照整合性
- [references/ledger.md](references/ledger.md) — 台帳のパス・スキーマ・更新規則
- [references/worker-contract.md](references/worker-contract.md) — workerの構造化出力とwriter境界

## ワークフロー

### 1. 台帳から開始位置を決める

`ledger/<company_id>.yaml` を探す。企業名だけ与えられたときは `data/companies.csv` からIDを引く。

- 台帳がある: `phases` と各 `items` を読み、未完了laneをすべて特定する。完了済みphaseはやり直さず、必要なworkerだけを手順6で並列起動する。`ir` / `recruit` / `segments` がすべて `done` で、`phase: article` の全調査行も完了状態なら手順8へ進む。
- 台帳がない: 手順2から順に進む。

workerの再開条件は次のとおり。

| worker | 起動条件 |
| --- | --- |
| `company-ir-worker` | `phases.ir != done` |
| `company-recruit-worker` | `phases.recruit != done` |
| `company-profile-worker` | `phases.segments != done`、または `phase: article` に `pending` 行がある |

**完了条件**: 「新規開始」か、再開するworkerと後続フェーズを確定し、ユーザーへ報告している。

### 2. 変更範囲を確認する

Gitの未コミット変更を確認し、ユーザーの変更を上書きしない。
対象企業のIR行、必要なマスタ行、企業MDX、台帳以外を変更しない。

**完了条件**: 触ってよいファイルを列挙できる。

### 3. 既存状態を棚卸しする

IR用CSVから対象企業のID・主キー・年度・出典・業界・企業関係を確認する。
同名・旧社名・ブランド・同一URL・証券コード・法人番号で重複候補を探す。既存MDXと、移行元になる `yukijya_doh` の記事も確認する。

**完了条件**: 再利用する `company_id` が確定し、重複候補をすべて確認済み。

### 4. 企業境界とIDを確定する

採用主体、開示主体、ブランド・報告セグメント、親子関係、連結範囲、基準日、会計年度、会計基準、通貨、単位を固定する。
既存企業は既存 `company_id` を再利用する。社名変更や表記差で新IDを作らない。

外資系企業（日本法人と海外親会社が分かれる企業）は [references/foreign-companies.md](references/foreign-companies.md) の3層分離に従う。

**完了条件**: 各主体の `company_id` と `company_relations.csv` の関係が決まっている。

### 5. 台帳を作成する

[references/ledger.md](references/ledger.md) に従い、`ledger/<company_id>.yaml` へ全フェーズの調査行を立てる。**立てなかった要素は調査されない。**
この時点では調査枠だけを作り、値や出典を埋めるために採用サイトや事業サイトを調べ始めない。

**完了条件**: 台帳ファイルが存在し、ir・recruit・segments・article の全要素の行が `pending` で並んでいる。

### 6. 調査workerを並列実行する

起動対象のworkerに共通して、`company_id`、採用主体、開示主体、`project-root`、台帳パス、対象item ID、ユーザー指定を明示する。`fiscal-year` は `company-ir-worker` に引き渡す。

Taskを呼ぶ前に、この統括agentが起動対象のうち `done` でない `ir` / `recruit` / `segments` だけを `in_progress` にして `updated_at` を更新する。完了済みphaseを `in_progress` へ戻さない。`company-profile-worker` が記事材料を調べる段階では `phases.article` を変更しない。

利用可能な専用SubAgentを、1つのメッセージ内で同時にTask起動する。

| SubAgent | task promptに必ず含める内容 |
| --- | --- |
| `company-ir-worker` | `agents/agents/company-ir-worker.md` と `company-ir` を `mode=worker` で実行し、IR所有ファイルだけを更新する |
| `company-recruit-worker` | `agents/agents/company-recruit-worker.md` と `company-research` を `scope=recruit mode=worker` で実行し、ファイルは編集しない |
| `company-profile-worker` | `agents/agents/company-profile-worker.md` と `company-research` を `scope=segments mode=worker` で実行し、ファイルは編集しない |

専用SubAgentが現在のセッションに読み込まれていない場合は、同数の `general` SubAgentを同時起動し、それぞれのprompt冒頭で対応する `agents/agents/<name>.md` を読んで厳守させる。並列化のためにgit worktreeを分けず、writer境界で競合を防ぐ。

**完了条件**: 起動対象workerがすべて最終YAMLを返している。Taskを逐次起動していない。

### 7. worker結果を検査して台帳へ統合する

[worker結果契約](references/worker-contract.md) の受入検査を行う。IR workerについては、事前に記録した対象企業行と実際のCSV差分を比較し、主キー、`source_id`、行数、対象年度を再確認する。既存の未コミット変更をworkerの成果として数えない。

受入済みの結果だけを、この統括agentが台帳へ一括反映する。

- 全担当行が `done` または `not_disclosed` のphaseだけを `done` にする。
- `company-profile-worker` が返した `phase: article` の調査行は更新するが、`phases.article` は変更せず、記事完成時に `company-article` が確定する。
- `partial` / `blocked` / 契約違反のworkerがあれば、受入済み結果を保存し、同じTaskの継続または該当workerだけの再実行で解消する。他workerをやり直さない。
- workerが台帳、MDX、担当外ファイルを変更していた場合は統合せず、変更箇所を報告して停止する。ユーザーの既存変更は戻さない。

**完了条件**: `phases.ir` / `recruit` / `segments` が必要なfocusの範囲ですべて `done` で、`phase: article` の調査行もすべて `done` か `not_disclosed`。

### 8. company-article を実行する

前提phaseがすべて完了してから実行する。`validate` の指定があれば引き渡す。

**完了条件**: `phases.article` と `phases.verify` が `done`。

### 9. 結果を集約して報告する

**完了条件**: 「出力」の全項目を報告している。

## やらないこと

- 検索結果のスニペット、記憶、概算を根拠にしない。
- 評価・応募判断・投資判断をCSVへ保存しない。
- 企業・業界・IR出典を削除しない。削除やID変更が必要ならユーザーへ確認する。
- 既存ページを更新するとき、ユーザーが移行を求めない限りページ全体を機械的に書き換えない。
- 台帳を `data/` 配下へ置かない（`data/` はストレージへ同期される正本置き場）。

## 出力

- 台帳のパスと、各フェーズの完了状態
- 各workerと担当スキルの出力の集約（更新したCSV・MDX、実行したCLIと原本ID、指標カバレッジ、検算・テスト・ビルドの結果）
- 使用した `company_id` と `company_relations.csv` の関係（採用主体 / 開示主体 / 報告セグメント）

## 参照リソース

- [references/ledger.md](references/ledger.md): 調査台帳のパス・スキーマ・更新規則・立てるべき行。
- [references/foreign-companies.md](references/foreign-companies.md): 外資系企業の3層分離と海外法定開示の扱い。
- [references/worker-contract.md](references/worker-contract.md): SubAgentの出力形式・受入検査・writer境界。
