import { access } from "node:fs/promises";
import path from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

import { cloudflareConfig } from "../config/cloudflare.mjs";
import { getCloudflareApiToken } from "./lib/domain-manage-env.mjs";

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const wranglerConfigPath = path.join(rootDir, "wrangler.jsonc");
const wranglerCliPath = await resolveWranglerCli(rootDir);
const apiToken = getCloudflareApiToken();

await runWranglerDeploy();
await attachCustomDomain();

console.log(
  `Deployed ${cloudflareConfig.homepage.serviceName} to https://${cloudflareConfig.homepage.hostname}/`,
);

async function runWranglerDeploy() {
  const exitCode = await new Promise((resolve, reject) => {
    const child = spawn(
      process.execPath,
      [wranglerCliPath, "deploy", "--config", wranglerConfigPath],
      {
        cwd: rootDir,
        env: {
          ...process.env,
          CLOUDFLARE_API_TOKEN: apiToken,
          CLOUDFLARE_ACCOUNT_ID: cloudflareConfig.accountId,
        },
        stdio: "inherit",
      },
    );

    child.on("error", reject);
    child.on("exit", (code) => resolve(code ?? 1));
  });

  if (exitCode !== 0) {
    throw new Error(`wrangler deploy failed with exit code ${exitCode}.`);
  }
}

async function attachCustomDomain() {
  const response = await fetch(
    `https://api.cloudflare.com/client/v4/accounts/${cloudflareConfig.accountId}/workers/domains`,
    {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${apiToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        hostname: cloudflareConfig.homepage.hostname,
        service: cloudflareConfig.homepage.serviceName,
        zone_id: cloudflareConfig.zoneId,
        zone_name: cloudflareConfig.zoneName,
      }),
    },
  );

  const payload = await response.json();
  if (response.ok && payload?.success) {
    return;
  }

  const details = JSON.stringify(payload?.errors ?? payload, null, 2);
  throw new Error(`Failed to attach custom domain: ${details}`);
}

async function resolveWranglerCli(projectDir) {
  const absoluteCliPath = path.join(
    projectDir,
    "node_modules",
    "wrangler",
    "wrangler-dist",
    "cli.js",
  );
  await access(absoluteCliPath);
  return absoluteCliPath;
}
