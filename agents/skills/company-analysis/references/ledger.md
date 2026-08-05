# 調査台帳

企業1社の調査項目・進行状態・出典を記録する唯一の作業ファイル。
パスは `<project-root>/ledger/<company_id>.yaml`。`company_id` は採用主体のIDを使い、開示主体が別法人の場合は `disclosure_company_id` で指す。

台帳はgitへコミットし、調査来歴（どの公式ページをいつ確認したか）として残す。
`data/` はストレージへ同期される正本置き場なので、台帳を `data/` 配下に置かない。

## 保存先定義

| 内容 | 正本 |
| --- | --- |
| 企業ID・公式URL・業界・企業間の関係 | `companies.csv` / `company_industries.csv` / `company_relations.csv` |
| IR資料の識別情報 | `sources.csv` |
| 有報開示の財務・人的資本の数値 | `metrics.csv` |
| 年度別の報告セグメント | `segments.csv` |
| IR数値への比較上の注記 | `company_annotations.csv` |
| 理念・会社紹介・採用情報・サービス・関連企業 | `site/src/pages/companies/<company_id>.mdx` |
| 調査の進行状態・調査途中の事実・取得経路 | `ledger/<company_id>.yaml`（この台帳） |

## スキーマ

```yaml
company_id: hitachi                 # 採用主体のcompany_id。ファイル名と一致させる
disclosure_company_id: hitachi      # 財務を開示する法人のcompany_id
fiscal_year: 2026                   # 対象年度。未指定開始なら取得後に確定する
focus: 両方                          # 就活 | 投資 | 両方
created_at: 2026-08-05
updated_at: 2026-08-05              # 更新のたびに書き換える
phases:                             # pending | in_progress | done
  ir: pending
  recruit: pending
  segments: pending
  article: pending
  verify: pending
items:
  - id: ir-revenue                  # フェーズ接頭辞つきの一意ID
    phase: ir                       # ir | recruit | segments | article
    store: ir_csv                   # ir_csv | mdx
    topic: 売上収益 3期以上
    status: pending                 # pending | done | not_disclosed
    value: ""                       # 下記「valueの書き方」に従う
    subject: ""                     # 開示法人・連結単体・採用主体・対象職種など
    as_of: ""                       # 基準日・会計年度・募集年度・確認日
    unit: ""                        # 円、百万円、%、人、時間など
    source: ""                      # source_id、またはURL+公表日
    via: ""                         # 実行したCLI・引数・検索期間、またはクロール起点URL
    note: ""
```

### valueの書き方

- `phase: ir` の行はCSVが正本。値そのものは複写せず、保存先の所在（`metrics.csv` の対象年度・行数など）を書く。
- `phase: recruit` / `segments` の行は記事執筆の材料。原文の意味を変えない要約または数値を書く。記事完成後もそのまま残す。
- `status: not_disclosed` の行は、開示がないと確認した公式資料・ページを `note` へ書く。

## 更新規則

- 台帳の作成は `company-analysis`（統括）が一度だけ行う。単独フェーズの実行で台帳がない場合だけ、担当フェーズの行に限って新規作成してよい。
- 単独実行の各スキルは開始時に担当 `phases` を `in_progress` にし、担当する全 `items` が `pending` でなくなったら `done` にして、`updated_at` を更新する。
- `company-analysis` が並列workerを使う場合、台帳のwriterは統括agentだけとする。統括agentがworker起動前に未完了の `ir` / `recruit` / `segments` だけを `in_progress` にし、[worker結果契約](worker-contract.md) の受入検査後に担当行とphaseをまとめて更新する。記事材料の調査中は `phases.article` を変更しない。
- `mode=worker` の担当agentは台帳を読み取り専用とし、`phases`、`items`、`updated_at` を変更しない。read-only workerは他のプロジェクトファイルも変更しない。
- `status` の完了は「`done`（値と出典が埋まった）」か「`not_disclosed`（開示がないと公式資料で確認した）」のどちらか。推定値・前年度流用・親会社の値で埋めない。
- 行は追記・更新のみ。他フェーズの行や完了済みの値を削除・上書きしない。
- worker結果に `pending` が残るphaseは `done` にしない。中断時は受入済みの調査結果だけを保存し、次回は未完了のworkerだけを再実行する。

## 立てるべき行

台帳作成時に、少なくとも次の行を `pending` で立てる。開示・記載がない項目も行を立て、調査後に `not_disclosed` へ倒す。

### ir（store=ir_csv）

原則3期以上。キーごとの充足基準は [mdx-templateの棒グラフ表](../../company-article/references/mdx-template.md) に従う。

- 人的資本: 平均年間給与、平均年齢、平均勤続年数、従業員数
- 損益: 売上高、営業利益（または事業利益）
- 健全性: 自己資本比率、流動資産、流動負債、当座資産（算定内訳を `note` へ）
- キャッシュフロー: 営業・投資・財務
- セグメント: 報告セグメント名、セグメント別売上・利益
- 注記: 組織再編、会計基準変更、比較上の注記（`company_annotations.csv`）

### recruit（store=mdx）

- 採用主体、募集年度、確認日、募集ページURL
- 職種ごと: 仕事内容、応募資格、配属・選考区分、勤務地
- 職種ごと: 基準給与、基礎給、固定時間外手当、賞与、諸手当、標準年収
- 転勤、リモート勤務、標準労働時間、応募期限

### segments（store=mdx）

- 報告セグメントごとの具体的なサービス名、ブランド名、提供内容、運営法人
- 公式サイトの事業区分とIRの報告セグメントの対応関係と差異
- 関連企業（親会社・主な子会社と各社の事業内容）

### article（store=mdx）

- 理念・ミッション・スローガン（公式表記）
- 会社紹介（設立経緯・規模）
- 公式リンク（HP、IR、有価証券報告書PDF全年度、採用情報、新卒採用）

企業境界（正式社名、親子関係、連結範囲、ブランドと報告セグメントの対応、合併・分社化・会計基準変更による比較不能期間）は `items` ではなく準備フェーズで確定し、`company_relations.csv` と `note` へ記録する。外資系企業は [foreign-companies.md](foreign-companies.md) の3層を台帳の別行にする。
