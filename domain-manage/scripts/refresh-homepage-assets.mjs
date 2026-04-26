import path from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

import {
  verifyHomepageAssets,
  verifyHomepageDistAssets,
} from "./lib/homepage-assets.mjs";

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const distDir = path.join(rootDir, "dist");
const buildScriptPath = path.join(rootDir, "scripts", "build-worker.mjs");

const sourceAssets = await verifyHomepageAssets();
await runNodeScript(buildScriptPath);
const distAssets = await verifyHomepageDistAssets(distDir);

console.log(
  JSON.stringify(
    {
      ok: true,
      action: "refresh-homepage-assets",
      message:
        "Homepage dist assets were regenerated from curated assets/homepage files.",
      sourceAssetCount: sourceAssets.all.length,
      distAssetCount: distAssets.all.length,
      desktopBackgrounds: distAssets.desktopBackgrounds.map((asset) => ({
        assetPath: asset.assetPath,
        bytes: asset.outputBytes,
        hash: asset.outputHash,
      })),
      mobileHero: {
        assetPath: distAssets.mobileHero.assetPath,
        bytes: distAssets.mobileHero.outputBytes,
        hash: distAssets.mobileHero.outputHash,
      },
    },
    null,
    2,
  ),
);

async function runNodeScript(scriptPath) {
  const exitCode = await new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [scriptPath], {
      cwd: rootDir,
      stdio: "inherit",
    });
    child.on("error", reject);
    child.on("exit", (code) => resolve(code ?? 1));
  });
  if (exitCode !== 0) {
    throw new Error(`${path.relative(rootDir, scriptPath)} failed with exit code ${exitCode}.`);
  }
}
