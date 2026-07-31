import { defineConfig } from "astro/config";
import mdx from "@astrojs/mdx";
import tailwindcss from "@tailwindcss/vite";
import { unified } from "@astrojs/markdown-remark";
import remarkMath from "remark-math";
import remarkDirective from "remark-directive";
import rehypeKatex from "rehype-katex";
import remarkAdmonition from "./src/lib/remark-admonition.mjs";

export default defineConfig({
  output: "static",
  trailingSlash: "always",
  integrations: [mdx()],
  vite: {
    plugins: [tailwindcss()],
  },
  markdown: {
    processor: unified({
      remarkPlugins: [remarkMath, remarkDirective, remarkAdmonition],
      rehypePlugins: [rehypeKatex],
    }),
  },
});
