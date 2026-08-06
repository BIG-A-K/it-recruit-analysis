import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { defineConfig } from "astro/config";
import mdx from "@astrojs/mdx";
import sitemap from "@astrojs/sitemap";
import Papa from "papaparse";
import tailwindcss from "@tailwindcss/vite";
import { unified } from "@astrojs/markdown-remark";
import remarkMath from "remark-math";
import remarkDirective from "remark-directive";
import rehypeKatex from "rehype-katex";
import remarkAdmonition from "./src/lib/remark-admonition.mjs";

const dataDirectory = fileURLToPath(new URL("../data/", import.meta.url));

// data/ は site/ の外にあり Vite の監視対象に入らないため、CSV を直しても
// src/lib/data/index.ts の評価結果がキャッシュされたままになる。
// 一度パースエラーになると CSV 修正後も dev サーバーがエラーを返し続けるので、
// 監視対象に加えて変更時にサーバーを再起動する。
function watchDataCsv() {
  return {
    name: "watch-data-csv",
    apply: "serve",
    configureServer(server) {
      server.watcher.add(dataDirectory);
      const restart = (file) => {
        if (file.startsWith(dataDirectory) && file.endsWith(".csv")) {
          server.restart();
        }
      };
      server.watcher.on("change", restart);
      server.watcher.on("add", restart);
      server.watcher.on("unlink", restart);
    },
  };
}

// is_active=false の企業ページは noindex で配信しているため、sitemap からも外す。
// 載せたままだと Search Console で「送信された URL が noindex」の警告になる。
const noindexPaths = new Set(
  Papa.parse(readFileSync(`${dataDirectory}companies.csv`, "utf8"), {
    header: true,
    skipEmptyLines: true,
  })
    .data.filter((row) => row.is_active !== "true")
    .map((row) => `/companies/${row.company_id}/`),
);

export default defineConfig({
  site: "https://recruit.big-a-k.com",
  output: "static",
  trailingSlash: "always",
  integrations: [
    mdx(),
    sitemap({ filter: (page) => !noindexPaths.has(new URL(page).pathname) }),
  ],
  vite: {
    plugins: [tailwindcss(), watchDataCsv()],
  },
  markdown: {
    processor: unified({
      remarkPlugins: [remarkMath, remarkDirective, remarkAdmonition],
      rehypePlugins: [rehypeKatex],
    }),
  },
});
