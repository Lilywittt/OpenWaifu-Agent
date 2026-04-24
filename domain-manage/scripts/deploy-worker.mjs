import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { cloudflareConfig } from "../config/cloudflare.mjs";

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const workerPath = path.join(rootDir, "dist", "worker.js");
const apiToken = process.env.CLOUDFLARE_API_TOKEN;
const { homepage } = cloudflareConfig;

if (!apiToken) {
  console.error("Missing CLOUDFLARE_API_TOKEN.");
  process.exit(1);
}

const workerSource = await readFile(workerPath, "utf8");

await uploadWorker(workerSource);
await attachDomain();

console.log(`Deployed ${homepage.serviceName} to https://${homepage.hostname}/`);

async function uploadWorker(source) {
  const response = await fetch(
    `https://api.cloudflare.com/client/v4/accounts/${cloudflareConfig.accountId}/workers/scripts/${homepage.serviceName}`,
    {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${apiToken}`,
        "Content-Type": "application/javascript",
      },
      body: source,
    },
  );

  const payload = await response.json();
  ensureSuccess(response, payload, "upload worker");
}

async function attachDomain() {
  const response = await fetch(
    `https://api.cloudflare.com/client/v4/accounts/${cloudflareConfig.accountId}/workers/domains`,
    {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${apiToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        hostname: homepage.hostname,
        service: homepage.serviceName,
        zone_id: cloudflareConfig.zoneId,
        zone_name: cloudflareConfig.zoneName,
      }),
    },
  );

  const payload = await response.json();
  ensureSuccess(response, payload, "attach domain");
}

function ensureSuccess(response, payload, action) {
  if (response.ok && payload?.success) {
    return;
  }

  const details = JSON.stringify(payload?.errors ?? payload, null, 2);
  throw new Error(`Failed to ${action}: ${details}`);
}
