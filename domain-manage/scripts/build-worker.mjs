import { mkdir, rm, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { homepageGalleryConfig } from "../config/homepage-gallery.mjs";
import { copyHomepageAssetsToDist } from "./lib/homepage-assets.mjs";

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const distDir = path.join(rootDir, "dist");
const previewHtmlPath = path.join(distDir, "index.html");
const outputPath = path.join(distDir, "worker.js");
const workerSizeLimitBytes = 3 * 1024 * 1024;

const homepageTitle = "OpenWaifu-Agent";
const homepageSubtitle = "\u81ea\u7531\u7684\u63d2\u753b\u8bbe\u8ba1 AI \u667a\u80fd\u4f53";
const metaDescription = `OpenWaifu-Agent ${homepageSubtitle}`;
const repositoryLabel = "\u5f00\u6e90\u4ed3\u5e93\uff1a";
const workbenchEntryLabel = "\u8fdb\u5165\u5de5\u4f5c\u53f0";

const repositoryUrl = normalizeExternalUrl(
  homepageGalleryConfig.repositoryUrl,
  "repositoryUrl",
);
const workbenchUrl = normalizeExternalUrl(
  homepageGalleryConfig.workbenchUrl,
  "workbenchUrl",
);

await rm(distDir, { recursive: true, force: true });
await mkdir(distDir, { recursive: true });

const copiedAssets = await copyHomepageAssetsToDist(distDir);
const mobileHero = copiedAssets.mobileHero;
const desktopBackgrounds = copiedAssets.desktopBackgrounds.map((item, index) => ({
  ...item,
  slotClass: `gallery-slot-${index + 1}`,
}));

const preloadMarkup = [mobileHero, ...desktopBackgrounds.slice(0, 2)]
  .map(
    (item) =>
      `    <link rel="preload" as="image" href="${escapeHtmlAttribute(item.publicPath)}" />`,
  )
  .join("\n");

const galleryMarkup = desktopBackgrounds
  .map(
    (item) => `<div
          class="gallery-slot ${item.slotClass}"
          style="${escapeHtmlAttribute(buildGallerySlotStyle(item))}"
          aria-hidden="true"
        ></div>`,
  )
  .join("\n        ");

const html = `<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>${escapeHtml(homepageTitle)}</title>
    <meta name="description" content="${escapeHtmlAttribute(metaDescription)}" />
    <meta name="theme-color" content="#050813" />
${preloadMarkup}
    <style>
      :root {
        color-scheme: dark;
        --bg: #050813;
        --text: #f7f8ff;
        --muted: rgba(233, 237, 255, 0.84);
        --line: rgba(255, 255, 255, 0.12);
        --panel-shadow: 0 28px 90px rgba(2, 8, 24, 0.42);
        --button-bg: linear-gradient(135deg, #f6f7ff, #c9d5ff 38%, #8be0ff);
        --button-text: #08111f;
        --button-shadow: 0 16px 36px rgba(95, 162, 255, 0.24);
        --hero-width: min(100%, 700px);
      }

      * {
        box-sizing: border-box;
      }

      html,
      body {
        min-height: 100%;
        background: var(--bg);
      }

      body {
        margin: 0;
        font-family: "Aptos", "Segoe UI Variable Text", "PingFang SC", "Microsoft YaHei", sans-serif;
        color: var(--text);
      }

      a {
        color: inherit;
      }

      .hero-page {
        min-height: 100vh;
        position: relative;
        isolation: isolate;
        overflow: hidden;
        background:
          radial-gradient(circle at top right, rgba(137, 224, 255, 0.18), transparent 24%),
          radial-gradient(circle at left center, rgba(255, 198, 223, 0.16), transparent 30%),
          linear-gradient(135deg, #050813 0%, #0c1226 42%, #060913 100%);
      }

      .gallery-shell {
        position: absolute;
        inset: 0;
        padding: clamp(18px, 2vw, 28px);
      }

      .gallery-shell::before {
        content: "";
        position: absolute;
        inset: 0;
        background:
          linear-gradient(90deg, rgba(5, 8, 19, 0.9) 0%, rgba(5, 8, 19, 0.62) 26%, rgba(5, 8, 19, 0.28) 52%, rgba(5, 8, 19, 0.74) 100%),
          linear-gradient(180deg, rgba(5, 8, 19, 0.12) 0%, rgba(5, 8, 19, 0.54) 100%);
        z-index: 1;
        pointer-events: none;
      }

      .gallery {
        position: relative;
        z-index: 0;
        display: grid;
        grid-template-columns: 1.16fr 0.92fr 1.05fr 0.88fr 0.82fr;
        gap: clamp(12px, 1.4vw, 20px);
        height: 100%;
      }

      .gallery-slot {
        min-width: 0;
        border: 1px solid var(--line);
        border-radius: 30px;
        overflow: hidden;
        background-color: rgba(7, 10, 20, 0.86);
        background-image:
          linear-gradient(180deg, rgba(255, 255, 255, 0.04), rgba(7, 10, 20, 0.18)),
          var(--slot-image);
        background-size: cover;
        background-repeat: no-repeat;
        background-position: var(--slot-position, 50% 50%);
        box-shadow:
          inset 0 1px 0 rgba(255, 255, 255, 0.08),
          0 24px 64px rgba(2, 8, 24, 0.24);
      }

      .gallery-slot-1 {
        margin-top: 4vh;
        margin-bottom: 10vh;
      }

      .gallery-slot-2 {
        margin-top: 18vh;
        margin-bottom: 3vh;
      }

      .gallery-slot-3 {
        margin-top: 8vh;
        margin-bottom: 16vh;
      }

      .gallery-slot-4 {
        margin-top: 24vh;
        margin-bottom: 5vh;
      }

      .gallery-slot-5 {
        margin-top: 14vh;
        margin-bottom: 22vh;
      }

      .content-shell {
        position: relative;
        z-index: 2;
        min-height: 100vh;
        display: flex;
        align-items: center;
        padding: clamp(28px, 5vw, 72px);
      }

      .hero-card {
        width: var(--hero-width);
        display: grid;
        gap: 18px;
        padding: clamp(28px, 3vw, 42px);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 32px;
        background:
          linear-gradient(180deg, rgba(10, 14, 30, 0.8), rgba(10, 14, 30, 0.56)),
          radial-gradient(circle at top, rgba(154, 197, 255, 0.14), transparent 54%);
        box-shadow: var(--panel-shadow);
        backdrop-filter: blur(22px);
      }

      h1 {
        margin: 0;
        display: grid;
        gap: 10px;
        font-family: "Iowan Old Style", "Palatino Linotype", "Noto Serif SC", "Songti SC", serif;
        line-height: 0.94;
        text-wrap: balance;
        text-shadow: 0 12px 42px rgba(0, 0, 0, 0.34);
      }

      .title-main {
        display: block;
        font-size: clamp(3.5rem, 6vw, 6.6rem);
        font-weight: 700;
      }

      .title-sub {
        display: block;
        font-size: clamp(1.2rem, 2.15vw, 2.2rem);
        font-weight: 500;
        color: rgba(246, 248, 255, 0.96);
      }

      .repo {
        margin: 0;
        font-size: clamp(0.92rem, 1.2vw, 1.05rem);
        line-height: 1.7;
        color: var(--muted);
      }

      .repo a {
        text-decoration-color: rgba(255, 255, 255, 0.34);
        text-underline-offset: 0.18em;
        overflow-wrap: anywhere;
      }

      .entry-row {
        display: flex;
        flex-wrap: wrap;
        gap: 14px;
        align-items: center;
      }

      .entry {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 148px;
        min-height: 54px;
        padding: 0 26px;
        border-radius: 999px;
        font-size: 1rem;
        font-weight: 700;
        color: var(--button-text);
        background: var(--button-bg);
        box-shadow: var(--button-shadow);
        text-decoration: none;
        transition:
          transform 180ms ease,
          box-shadow 180ms ease,
          filter 180ms ease;
      }

      .entry:hover,
      .entry:focus-visible {
        transform: translateY(-2px);
        box-shadow: 0 20px 44px rgba(95, 162, 255, 0.32);
        filter: brightness(1.03);
      }

      @media (max-width: 1480px) {
        .gallery {
          grid-template-columns: 1.15fr 0.94fr 1.02fr 0.84fr;
        }

        .gallery-slot-5 {
          display: none;
        }
      }

      @media (max-width: 1180px) {
        .gallery {
          grid-template-columns: 1.1fr 0.95fr 0.98fr;
        }

        .gallery-slot-4,
        .gallery-slot-5 {
          display: none;
        }
      }

      @media (max-width: 920px) {
        .gallery-shell {
          display: none;
        }

        .hero-page {
          background:
            linear-gradient(180deg, rgba(7, 10, 20, 0.24) 0%, rgba(7, 10, 20, 0.62) 54%, rgba(7, 10, 20, 0.9) 100%),
            radial-gradient(circle at top, rgba(152, 221, 255, 0.22), transparent 34%),
            url("${mobileHero.publicPath}") center center / cover no-repeat;
        }

        .content-shell {
          align-items: flex-end;
          justify-content: center;
          padding: 18px;
        }

        .hero-card {
          width: min(100%, 420px);
          gap: 16px;
          padding: 22px 20px 20px;
          border-radius: 26px;
          background:
            linear-gradient(180deg, rgba(9, 13, 28, 0.64), rgba(9, 13, 28, 0.82)),
            radial-gradient(circle at top, rgba(170, 197, 255, 0.16), transparent 56%);
          backdrop-filter: blur(18px);
        }

        h1 {
          gap: 8px;
        }

        .title-main {
          font-size: clamp(2.35rem, 11vw, 3.4rem);
        }

        .title-sub {
          font-size: clamp(1.05rem, 5vw, 1.4rem);
          line-height: 1.18;
        }

        .repo {
          font-size: 0.92rem;
          line-height: 1.6;
        }

        .entry {
          min-width: 100%;
          min-height: 52px;
        }
      }

      @media (max-width: 420px) {
        .content-shell {
          padding: 14px;
        }

        .hero-card {
          padding: 18px 16px 16px;
        }
      }
    </style>
  </head>
  <body>
    <div class="hero-page">
      <div class="gallery-shell" aria-hidden="true">
        <div class="gallery">
          ${galleryMarkup}
        </div>
      </div>
      <main class="content-shell">
        <section class="hero-card">
          <h1>
            <span class="title-main">${escapeHtml(homepageTitle)}</span>
            <span class="title-sub">${escapeHtml(homepageSubtitle)}</span>
          </h1>
          <p class="repo">${escapeHtml(repositoryLabel)}<a href="${escapeHtmlAttribute(repositoryUrl)}">${escapeHtml(repositoryUrl)}</a></p>
          <div class="entry-row">
            <a class="entry" href="${escapeHtmlAttribute(workbenchUrl)}">${escapeHtml(workbenchEntryLabel)}</a>
          </div>
        </section>
      </main>
    </div>
  </body>
</html>
`;

const workerSource = `const RESPONSE_SECURITY_HEADERS = {
  "Content-Security-Policy":
    "default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'; upgrade-insecure-requests",
  "Permissions-Policy":
    "accelerometer=(), autoplay=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "Cross-Origin-Resource-Policy": "same-origin"
};

const HTML_CACHE_CONTROL = "public, max-age=0, must-revalidate";
const ASSET_CACHE_CONTROL = "public, max-age=31536000, immutable";

export default {
  async fetch(request, env) {
    if (!["GET", "HEAD"].includes(request.method)) {
      return new Response("Method Not Allowed", {
        status: 405,
        headers: {
          Allow: "GET, HEAD",
          "Content-Type": "text/plain; charset=UTF-8",
          "Cache-Control": HTML_CACHE_CONTROL
        }
      });
    }

    const requestUrl = new URL(request.url);
    const assetRequest = requestUrl.pathname === "/"
      ? new Request(new URL("/index.html", requestUrl), request)
      : request;

    const response = await env.ASSETS.fetch(assetRequest);
    const responseUrl = new URL(assetRequest.url);
    const headers = new Headers(response.headers);
    const cacheControl = response.ok && responseUrl.pathname.startsWith("/assets/")
      ? ASSET_CACHE_CONTROL
      : HTML_CACHE_CONTROL;

    for (const [key, value] of Object.entries(RESPONSE_SECURITY_HEADERS)) {
      headers.set(key, value);
    }
    headers.set("Cache-Control", cacheControl);

    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers
    });
  }
};
`;

await writeFile(previewHtmlPath, html, "utf8");
await writeFile(outputPath, workerSource, "utf8");

const workerStat = await stat(outputPath);
if (workerStat.size > workerSizeLimitBytes) {
  throw new Error(
    `Worker bundle exceeds ${workerSizeLimitBytes} bytes: ${workerStat.size}`,
  );
}

console.log(`Built ${path.relative(rootDir, outputPath)} (${formatBytes(workerStat.size)})`);
console.log(`Preview ${path.relative(rootDir, previewHtmlPath)}`);

function buildGallerySlotStyle(item) {
  const position = String(item.backgroundPosition ?? "50% 50%");
  return `--slot-image: url('${item.publicPath}'); --slot-position: ${position};`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function escapeHtmlAttribute(value) {
  return escapeHtml(value).replaceAll("'", "&#39;");
}

function normalizeExternalUrl(rawValue, fieldName) {
  const url = new URL(String(rawValue ?? "").trim());
  if (!["http:", "https:"].includes(url.protocol)) {
    throw new Error(`${fieldName} must use http or https.`);
  }
  return url.toString();
}

function formatBytes(size) {
  if (size < 1024) {
    return `${size} B`;
  }
  const kib = size / 1024;
  if (kib < 1024) {
    return `${kib.toFixed(1)} KiB`;
  }
  return `${(kib / 1024).toFixed(2)} MiB`;
}
