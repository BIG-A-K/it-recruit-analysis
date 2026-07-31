import { visit } from "unist-util-visit";

/**
 * `:::warning` のようなディレクティブを警告ボックスの markup に変換する。
 *
 *   :::warning
 *   非上場のため法定開示はない。
 *   :::
 *
 * 1 行だけなら `::warning[本文]` の leaf directive も使える。
 */

// 別名は同じ見た目に寄せる。値は CSS の修飾子
const KINDS = {
  warning: "warning",
  warn: "warning",
  caution: "warning",
  info: "info",
  note: "info",
  tip: "info",
  danger: "danger",
  error: "danger",
  important: "danger",
};

export default function remarkAdmonition() {
  return (tree, file) => {
    visit(tree, (node) => {
      if (node.type !== "containerDirective" && node.type !== "leafDirective") {
        return;
      }
      const kind = KINDS[node.name];
      if (!kind) {
        // 名前の打ち間違いは既定の <div> になって気づけないので警告する
        file.message(
          `未対応のディレクティブ :::${node.name} です（${Object.keys(KINDS).join(", ")}）`,
          node,
        );
        return;
      }

      // `::warning[本文]` は [] の中身がインラインのまま children に入る
      if (node.type === "leafDirective") {
        node.children = node.children.length > 0
          ? [{ type: "paragraph", children: node.children }]
          : [];
      }

      if (node.children.length === 0) {
        file.message(`:::${node.name} の中身が空です`, node);
      }

      node.data = {
        ...node.data,
        hName: "div",
        hProperties: { className: ["admonition", `admonition-${kind}`] },
      };
    });
  };
}
