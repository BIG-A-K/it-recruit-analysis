/**
 * 検索の表記ゆれを吸収する正規化。
 * 全角と半角、大文字と小文字、カタカナとひらがなを寄せ、
 * 空白・中黒・各種ハイフン・長音は落として比較する。
 * ビルド時の検索キー生成と、ブラウザ側の入力の正規化で共有する。
 */
export const normalizeForSearch = (value: string): string =>
  value
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[ァ-ヶ]/g, (char) =>
      String.fromCharCode(char.charCodeAt(0) - 0x60),
    )
    .replace(/[\s・.,()（）「」【】\-‐‑–—ー]/g, "");
