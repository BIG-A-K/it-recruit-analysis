import { execFileSync } from "node:child_process";
import { existsSync, statSync } from "node:fs";
import { dirname, join } from "node:path";

const pageDirectory = "site/src/pages/companies";

function runGit(cwd: string, args: string[]): string | undefined {
  try {
    return execFileSync("git", args, {
      cwd,
      encoding: "utf-8",
      maxBuffer: 64 * 1024 * 1024,
      stdio: ["ignore", "pipe", "ignore"],
    });
  } catch {
    // gitが使えない環境ではファイルの更新時刻へフォールバックする
    return undefined;
  }
}

/**
 * ビルド後のチャンクは元のソースと階層が変わるため、`import.meta.url` からの
 * 相対位置ではなくカレントディレクトリを起点にリポジトリルートを探す。
 */
function findRepositoryRoot(): string {
  const fromGit = runGit(process.cwd(), ["rev-parse", "--show-toplevel"]);
  if (fromGit?.trim()) return fromGit.trim();

  let directory = process.cwd();
  for (let depth = 0; depth < 6; depth += 1) {
    if (existsSync(join(directory, pageDirectory))) return directory;
    const parent = dirname(directory);
    if (parent === directory) break;
    directory = parent;
  }
  return process.cwd();
}

const repositoryRoot = findRepositoryRoot();

function lastCommitDates(): Map<string, string> {
  const dates = new Map<string, string>();
  // 日付の行だけ "@" で始めて、続くファイル名の行と区別する
  const output = runGit(repositoryRoot, [
    "log",
    "--format=@%cI",
    "--name-only",
    "--",
    pageDirectory,
  ]);
  if (!output) return dates;

  let committedAt = "";
  for (const line of output.split("\n")) {
    if (line.startsWith("@")) {
      committedAt = line.slice(1);
      continue;
    }
    const match = line.match(/companies\/([^/]+)\.mdx$/);
    // git log は新しい順に並ぶため、最初に現れた日付がその記事の最終更新になる
    if (match && !dates.has(match[1])) dates.set(match[1], committedAt);
  }
  return dates;
}

function firstCommitDates(): Map<string, string> {
  const dates = new Map<string, string>();
  const output = runGit(repositoryRoot, [
    "log",
    "--diff-filter=A",
    "--format=@%cI",
    "--name-only",
    "--",
    pageDirectory,
  ]);
  if (!output) return dates;

  let committedAt = "";
  for (const line of output.split("\n")) {
    if (line.startsWith("@")) {
      committedAt = line.slice(1);
      continue;
    }
    const match = line.match(/companies\/([^/]+)\.mdx$/);
    // 再追加された記事でも、履歴上で最初に追加された日時を残す
    if (match) dates.set(match[1], committedAt);
  }
  return dates;
}

function locallyModifiedPages(): Set<string> {
  const modified = new Set<string>();
  const output = runGit(repositoryRoot, [
    "status",
    "--porcelain",
    "--",
    pageDirectory,
  ]);
  if (!output) return modified;

  for (const line of output.split("\n")) {
    const match = line.match(/companies\/([^/]+)\.mdx$/);
    if (match) modified.add(match[1]);
  }
  return modified;
}

function fileModifiedAt(companyId: string): string | undefined {
  try {
    return statSync(
      join(repositoryRoot, pageDirectory, `${companyId}.mdx`),
    ).mtime.toISOString();
  } catch {
    return undefined;
  }
}

const committedDates = lastCommitDates();
const firstCommittedDates = firstCommitDates();
const modifiedPages = locallyModifiedPages();

/** 企業記事が最初に追加された日時を返す。 */
export function companyPageAddedAt(companyId: string): string | undefined {
  return firstCommittedDates.get(companyId) ?? fileModifiedAt(companyId);
}

/**
 * 企業記事の最終更新日を返す。クローン直後はファイルの更新時刻が
 * チェックアウト時刻になってしまうためコミット日時を優先し、
 * 未コミットの変更がある記事だけファイルの更新時刻を使う。
 */
export function companyPageUpdatedAt(companyId: string): string | undefined {
  if (!modifiedPages.has(companyId)) {
    const committed = committedDates.get(companyId);
    if (committed) return committed;
  }
  return fileModifiedAt(companyId) ?? committedDates.get(companyId);
}

const updatedAtFormatter = new Intl.DateTimeFormat("ja-JP", {
  year: "numeric",
  month: "long",
  day: "numeric",
  timeZone: "Asia/Tokyo",
});

export function formatUpdatedAt(isoDate: string): string {
  return updatedAtFormatter.format(new Date(isoDate));
}
