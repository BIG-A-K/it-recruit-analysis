"""企業記事の散文規範のうち、機械的に判定できる規則を検証する。

判定は `agents/skills/company-article/references/mdx-template.md`（正本）と
`agents/skills/company-article-check/references/prose-style.md` に対応する。
文意の評価が必要な項目は company-article-check の判断に残し、ここでは
誤検知なく落とせる表層の違反だけを扱う。
"""

import re
from pathlib import Path

COMPANY_PAGE_DIR = (
    Path(__file__).parents[1] / "site" / "src" / "pages" / "companies"
)

LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
QUOTED = re.compile(r"「[^」]*」|『[^』]*』")
DASH = re.compile(r"[—―]")
POLITE = re.compile(r"(です|ます|ました|ません|でしょう)(?=[。、）」]|$)")
LINK_ONLY_PARAGRAPH = re.compile(r"^\[[^\]]+\]\([^)]+\)[。、]?$")

# MT「禁止する言い回し」。調査実況・伝聞の前置き・読者への案内にあたる。
BANNED_PHRASES = (
    "確認しました",
    "確認した",
    "確認したところ",
    "照合した",
    "によると",
    "とされています",
    "と説明しています",
    "が案内されています",
    "で確認できます",
    "に掲載されています",
    "を確認してください",
    "を参照してください",
)

# リンク先を開かなければ対象が分からないアンカーテキスト。
VAGUE_ANCHORS = ("こちら", "ここ", "リンク", "全文", "詳細", "続き")

MAX_SENTENCE_LENGTH = 100


def prose_lines(path: Path) -> list[tuple[int, str, bool, bool]]:
    """`CompanyProse` 内の読者向け行を (行番号, 行, 注記内, サイト節) で返す。

    コードブロック、frontmatter、import、コンポーネントタグ、公式の直接引用
    ブロックは散文として評価しない。
    """
    lines: list[tuple[int, str, bool, bool]] = []
    in_code = False
    in_prose = False
    in_directive = False
    in_site_section = False

    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if line == "<CompanyProse>":
            in_prose = True
            continue
        if line == "</CompanyProse>":
            in_prose = False
            continue
        if line.startswith(":::"):
            in_directive = line != ":::"
            continue
        if not in_prose or not line:
            continue
        if line.startswith(("<", "import ", ">")):
            continue
        if line.startswith("#"):
            in_site_section = "サイト" in line
            continue
        lines.append((number, line, in_directive, in_site_section))
    return lines


def company_pages() -> list[Path]:
    return sorted(COMPANY_PAGE_DIR.glob("*.mdx"))


def plain_text(line: str) -> str:
    """リンクを表示テキストへ落とした行を返す。"""
    return LINK.sub(r"\1", line)


def format_violations(violations: list[str]) -> str:
    return "\n".join(["", *violations])


def test_no_banned_phrases() -> None:
    """調査実況・伝聞の前置き・読者への案内を本文へ書かない。"""
    violations = []
    for path in company_pages():
        for number, line, _, _ in prose_lines(path):
            text = QUOTED.sub("", plain_text(line))
            for phrase in BANNED_PHRASES:
                if phrase in text:
                    violations.append(f"{path.name}:{number} 「{phrase}」 {text[:60]}")
    assert not violations, format_violations(violations)


def test_prose_uses_plain_form() -> None:
    """地の文は常体で書く。注記内の敬体と公式の直接引用は対象外とする。"""
    violations = []
    for path in company_pages():
        for number, line, in_directive, _ in prose_lines(path):
            if in_directive:
                continue
            text = QUOTED.sub("", plain_text(line))
            if POLITE.search(text):
                violations.append(f"{path.name}:{number} {text[:60]}")
    assert not violations, format_violations(violations)


def test_no_dash_in_prose() -> None:
    """日本語の地の文でダッシュを使わない。表のセルと直接引用は対象外とする。"""
    violations = []
    for path in company_pages():
        for number, line, _, _ in prose_lines(path):
            text = plain_text(line)
            if text.startswith("|"):
                continue
            if DASH.search(QUOTED.sub("", text)):
                violations.append(f"{path.name}:{number} {text[:60]}")
    assert not violations, format_violations(violations)


def test_links_do_not_replace_explanation() -> None:
    """リンクは根拠の所在であり、説明の代わりにしない。

    リンクだけの段落と、リンク先を開かなければ対象が分からないアンカー
    テキストを禁じる。`## サイト` のリンク集と、募集職種のように名称自体が
    対象を示す箇条書きは対象外とする。
    """
    violations = []
    for path in company_pages():
        for number, line, _, in_site_section in prose_lines(path):
            if in_site_section:
                continue
            if not line.startswith(("-", "*")) and LINK_ONLY_PARAGRAPH.match(line):
                violations.append(
                    f"{path.name}:{number} 段落がリンクだけになっている {line[:60]}"
                )
            for anchor in LINK.findall(line):
                label = anchor.strip()
                if label in VAGUE_ANCHORS or label.endswith("はこちら"):
                    violations.append(
                        f"{path.name}:{number} 対象が分からないリンク文言 [{label}]"
                    )
    assert not violations, format_violations(violations)


def test_sentences_are_not_too_long() -> None:
    """一文が長くなりすぎないようにする。表・箇条書き・直接引用は対象外とする。"""
    violations = []
    for path in company_pages():
        for number, line, _, _ in prose_lines(path):
            text = plain_text(line)
            if text.startswith(("|", "-", "*")):
                continue
            for sentence in QUOTED.sub("", text).split("。"):
                if len(sentence.strip()) > MAX_SENTENCE_LENGTH:
                    violations.append(
                        f"{path.name}:{number} ({len(sentence.strip())}字) "
                        f"{sentence.strip()[:60]}"
                    )
    assert not violations, format_violations(violations)
