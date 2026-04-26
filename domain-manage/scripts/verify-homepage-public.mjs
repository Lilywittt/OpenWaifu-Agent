import { createHash } from "node:crypto";

import { cloudflareConfig } from "../config/cloudflare.mjs";
import {
  hashFile,
  verifyHomepageAssets,
} from "./lib/homepage-assets.mjs";

const homepageUrl = new URL(`https://${cloudflareConfig.homepage.hostname}/`);
const cacheBust = Date.now().toString(36);
const maxAttempts = 6;
const retryDelayMs = 2500;

const localAssets = await verifyHomepageAssets();
const html = await fetchTextWithRetry(new URL(`/?verify=${cacheBust}`, homepageUrl));
const missingReferences = localAssets.all
  .filter((asset) => !html.includes(asset.assetPath))
  .map((asset) => asset.assetPath);
const legacyJpgReference = /assets\/homepage\/backgrounds\/scene-[1-5]\.jpg/.test(html);

if (missingReferences.length > 0 || legacyJpgReference) {
  throw new Error(
    [
      missingReferences.length
        ? `Homepage HTML is missing asset references: ${missingReferences.join(", ")}`
        : "",
      legacyJpgReference ? "Homepage HTML still references legacy scene jpg files." : "",
    ]
      .filter(Boolean)
      .join(" "),
  );
}

const assetRecords = [];
const mismatches = [];
for (const asset of localAssets.all) {
  const publicUrl = new URL(`/${asset.assetPath}?verify=${cacheBust}`, homepageUrl);
  const [localHash, publicPayload] = await Promise.all([
    hashFile(asset.absolutePath),
    fetchBinaryWithRetry(publicUrl),
  ]);
  const publicHash = createHash("sha256")
    .update(publicPayload.body)
    .digest("hex")
    .toUpperCase();
  const record = {
    id: asset.id,
    role: asset.role ?? "",
    assetPath: asset.assetPath,
    publicUrl: publicUrl.toString(),
    localHash,
    publicHash,
    publicBytes: publicPayload.body.byteLength,
    contentType: publicPayload.contentType,
    cacheControl: publicPayload.cacheControl,
    match: localHash === publicHash,
  };
  assetRecords.push(record);
  if (!record.match) {
    mismatches.push(record);
  }
}

if (mismatches.length > 0) {
  throw new Error(
    `Public homepage assets do not match curated assets: ${mismatches
      .map((item) => item.assetPath)
      .join(", ")}`,
  );
}

console.log(
  JSON.stringify(
    {
      ok: true,
      homepage: homepageUrl.toString(),
      htmlBytes: Buffer.byteLength(html, "utf8"),
      assetCount: assetRecords.length,
      mobileHero: assetRecords[0],
      desktopBackgrounds: assetRecords.slice(1),
    },
    null,
    2,
  ),
);

async function fetchTextWithRetry(url) {
  const payload = await fetchWithRetry(url);
  return payload.body.toString("utf8");
}

async function fetchBinaryWithRetry(url) {
  return fetchWithRetry(url);
}

async function fetchWithRetry(url) {
  let lastError = null;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      const response = await fetch(url, {
        headers: {
          "Cache-Control": "no-cache",
        },
      });
      const body = Buffer.from(await response.arrayBuffer());
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${body.toString("utf8").slice(0, 500)}`);
      }
      return {
        body,
        contentType: response.headers.get("content-type") ?? "",
        cacheControl: response.headers.get("cache-control") ?? "",
      };
    } catch (error) {
      lastError = error;
      if (attempt < maxAttempts) {
        await sleep(retryDelayMs);
      }
    }
  }
  throw lastError;
}

function sleep(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}
