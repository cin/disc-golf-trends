import { defineConfig, type Plugin } from "vitest/config";

// The built page may only run its own scripts and may not talk to any server, so a visitor's files cannot leave
// the tab. ('unsafe-inline' is for the dashboard's inline script and styles, which come from this repo.)
const CSP = [
  "default-src 'none'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data:",
  "connect-src 'none'",
  "form-action 'none'",
  "base-uri 'none'",
].join("; ");

const contentSecurityPolicy = (): Plugin => ({
  name: "content-security-policy",
  apply: "build",
  transformIndexHtml: () => [
    { tag: "meta", attrs: { "http-equiv": "Content-Security-Policy", content: CSP }, injectTo: "head-prepend" },
  ],
});

export default defineConfig({
  base: "./", // relative URLs, so the build works under https://<user>.github.io/<repo>/
  plugins: [contentSecurityPolicy()],
  server: { fs: { allow: [".."] } }, // the page imports the shared dashboard template and sample CSVs from the repo root
  build: { outDir: "dist", target: "es2022" },
  test: { include: ["tests/**/*.test.ts"], globalSetup: ["tests/tz.ts"] },
});
