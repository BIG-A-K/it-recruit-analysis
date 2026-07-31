#!/usr/bin/env bash
# data/*.csv を Cloudflare R2 へ同期する。認証情報はリポジトリ直下の .env から読む。
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
env_file="${ENV_FILE:-$repo_root/.env}"
data_dir="${DATA_DIR:-$repo_root/data}"
prefix="${R2_PREFIX-data}"

include_raw=0
extra_args=()

usage() {
  cat <<'USAGE'
使い方: scripts/sync-r2.sh [オプション] [-- aws s3 sync への追加引数]

  --dry-run       転送せず、対象だけを表示する
  --delete        ローカルにないオブジェクトをR2から削除する
  --include-raw   data/raw のEDINET原本も同期する
  -h, --help      このヘルプを表示する

環境変数: ENV_FILE / DATA_DIR / R2_PREFIX で既定値を上書きできる
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) extra_args+=(--dryrun); shift ;;
    --delete) extra_args+=(--delete); shift ;;
    --include-raw) include_raw=1; shift ;;
    -h|--help) usage; exit 0 ;;
    --) shift; extra_args+=("$@"); break ;;
    *) echo "不明なオプション: $1" >&2; usage >&2; exit 2 ;;
  esac
done

command -v aws >/dev/null || {
  echo "aws コマンドが見つかりません。AWS CLI v2 を入れてください。" >&2
  exit 1
}

# .env は KEY=VALUE 行だけを取り込む。値に # を含む鍵があるため行末コメントは解釈しない
if [[ -f "$env_file" ]]; then
  while IFS= read -r line; do
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" =~ ^[[:space:]]*[A-Za-z_][A-Za-z0-9_]*= ]] || continue
    key="${line%%=*}"
    value="${line#*=}"
    key="${key//[[:space:]]/}"
    value="${value%\"}"; value="${value#\"}"
    value="${value%\'}"; value="${value#\'}"
    # 既に環境変数がある場合はそちらを優先する（CIのシークレット等）
    [[ -n "${!key:-}" ]] || export "$key=$value"
  done <"$env_file"
fi

for name in R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY R2_ENDPOINT R2_BUCKET_NAME; do
  [[ -n "${!name:-}" ]] || { echo "$name が未設定です。$env_file に設定してください。" >&2; exit 1; }
done

destination="s3://$R2_BUCKET_NAME"
[[ -n "$prefix" ]] && destination="$destination/${prefix%/}"

if [[ $include_raw -eq 0 ]]; then
  # data/raw はEDINETから再取得できる原本のため既定では送らない
  extra_args+=(--exclude "raw/*")
  # 対象が .csv だけになるので文字コードまで明示する
  extra_args+=(--content-type "text/csv; charset=utf-8")
fi

# R2 は AWS CLI v2.23 以降が既定で付ける追加チェックサムを必要としない
export AWS_REQUEST_CHECKSUM_CALCULATION="${AWS_REQUEST_CHECKSUM_CALCULATION:-when_required}"
export AWS_RESPONSE_CHECKSUM_VALIDATION="${AWS_RESPONSE_CHECKSUM_VALIDATION:-when_required}"

AWS_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID" \
AWS_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY" \
AWS_DEFAULT_REGION=auto \
  aws s3 sync "$data_dir" "$destination" \
    --endpoint-url "$R2_ENDPOINT" \
    --exclude ".*" \
    --exclude "*/.*" \
    "${extra_args[@]}"

echo "synced $data_dir -> $destination"
