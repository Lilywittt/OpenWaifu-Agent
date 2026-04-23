import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const preferredImagePath = path.join(rootDir, "assets", "test-bg.jpg");
const fallbackImagePath = path.join(rootDir, "assets", "test.png");
const distDir = path.join(rootDir, "dist");
const outputPath = path.join(distDir, "worker.js");

let imagePath = preferredImagePath;
let imageMimeType = "image/jpeg";

try {
  await readFile(preferredImagePath);
} catch {
  imagePath = fallbackImagePath;
  imageMimeType = "image/png";
}

const imageBuffer = await readFile(imagePath);
const imageDataUri = `data:${imageMimeType};base64,${imageBuffer.toString("base64")}`;

const html = `<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>OpenWaifu-Agent</title>
    <meta name="description" content="OpenWaifu-Agent root entry." />
    <style>
      :root {
        color-scheme: dark;
        --text: #f5f8ff;
        --panel: rgba(3, 11, 23, 0.58);
        --panel-line: rgba(153, 206, 255, 0.28);
        --button-text: #04111f;
        --button-start: #f1f9ff;
        --button-end: #57b5ff;
        --shadow: 0 28px 80px rgba(2, 8, 18, 0.42);
      }

      * {
        box-sizing: border-box;
      }

      html,
      body {
        min-height: 100%;
      }

      body {
        margin: 0;
        font-family: "Aptos Display", "Segoe UI Variable Display", "PingFang SC", "Microsoft YaHei", sans-serif;
        color: var(--text);
        background:
          linear-gradient(180deg, rgba(2, 7, 16, 0.08) 0%, rgba(2, 7, 16, 0.24) 34%, rgba(2, 7, 16, 0.72) 100%),
          radial-gradient(circle at 50% 10%, rgba(75, 166, 255, 0.24), transparent 36%),
          url("${imageDataUri}") center 14% / cover no-repeat fixed;
      }

      .stage {
        min-height: 100vh;
        display: grid;
        place-items: end start;
        padding: clamp(24px, 4vw, 48px);
      }

      .panel {
        width: fit-content;
        max-width: min(100%, 880px);
        display: grid;
        justify-items: start;
        gap: 22px;
        padding: clamp(24px, 3.6vw, 40px);
        border: 1px solid rgba(153, 206, 255, 0.22);
        border-radius: 28px;
        background:
          linear-gradient(180deg, rgba(4, 10, 20, 0.7), rgba(4, 10, 20, 0.48)),
          radial-gradient(circle at center, rgba(42, 112, 196, 0.16), transparent 54%);
        box-shadow: var(--shadow);
        backdrop-filter: blur(18px);
      }

      h1 {
        margin: 0;
        font-size: clamp(3rem, 5.6vw, 5.8rem);
        line-height: 0.92;
        letter-spacing: -0.075em;
        white-space: nowrap;
        text-shadow: 0 8px 36px rgba(0, 0, 0, 0.34);
      }

      .entry {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 120px;
        min-height: 56px;
        padding: 0 28px;
        border-radius: 999px;
        font-size: 1.1rem;
        font-weight: 700;
        color: var(--button-text);
        background: linear-gradient(135deg, var(--button-start), var(--button-end));
        box-shadow: 0 16px 40px rgba(54, 158, 255, 0.34);
        text-decoration: none;
        transition:
          transform 180ms ease,
          box-shadow 180ms ease;
      }

      .entry:hover,
      .entry:focus-visible {
        transform: translateY(-2px);
        box-shadow: 0 20px 48px rgba(54, 158, 255, 0.42);
      }

      @media (max-width: 640px) {
        body {
          background-position: center 10%;
          background-attachment: scroll;
        }

        .stage {
          place-items: end center;
          padding: 18px;
        }

        .panel {
          width: min(100%, 360px);
          justify-items: center;
          text-align: center;
          gap: 18px;
          padding: 20px 22px;
          border-radius: 24px;
        }

        h1 {
          font-size: clamp(1.45rem, 6.8vw, 1.9rem);
        }
      }
    </style>
  </head>
  <body>
    <main class="stage">
      <section class="panel">
        <h1>OpenWaifu-Agent</h1>
        <a class="entry" href="https://hi.openwaifu-agent.uk">Hi</a>
      </section>
    </main>
  </body>
</html>
`;

const headers = {
  "Content-Type": "text/html; charset=UTF-8",
  "Cache-Control": "public, max-age=0, must-revalidate",
  "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'; upgrade-insecure-requests",
  "Permissions-Policy": "accelerometer=(), autoplay=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY"
};

const notFoundHeaders = {
  "Content-Type": "text/plain; charset=UTF-8",
  "Cache-Control": "public, max-age=0, must-revalidate",
  "X-Content-Type-Options": "nosniff"
};

const workerSource = `const HTML = ${JSON.stringify(html)};
const HTML_HEADERS = ${JSON.stringify(headers)};
const NOT_FOUND_HEADERS = ${JSON.stringify(notFoundHeaders)};

addEventListener("fetch", (event) => {
  event.respondWith(handleRequest(event.request));
});

async function handleRequest(request) {
  if (!["GET", "HEAD"].includes(request.method)) {
    return new Response("Method Not Allowed", {
      status: 405,
      headers: {
        Allow: "GET, HEAD",
        "Content-Type": "text/plain; charset=UTF-8"
      }
    });
  }

  const url = new URL(request.url);
  if (url.pathname !== "/" && url.pathname !== "/index.html") {
    return new Response("Not Found", {
      status: 404,
      headers: NOT_FOUND_HEADERS
    });
  }

  return new Response(request.method === "HEAD" ? null : HTML, {
    status: 200,
    headers: HTML_HEADERS
  });
}
`;

await mkdir(distDir, { recursive: true });
await writeFile(outputPath, workerSource, "utf8");

console.log(`Built ${path.relative(rootDir, outputPath)}`);
