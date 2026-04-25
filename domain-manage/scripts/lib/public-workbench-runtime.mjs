import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

import { cloudflareConfig } from "../../config/cloudflare.mjs";
import { domainManageDir } from "./workspace-paths.mjs";

const ingressRuntimeDir = path.join(domainManageDir, "runtime", "public_workbench_ingress");
const ingressRuntimePath = path.join(ingressRuntimeDir, "runtime.json");

export function getPublicWorkbenchIngressRuntimePath() {
  return ingressRuntimePath;
}

export async function loadPublicWorkbenchIngressRuntime() {
  try {
    const payload = JSON.parse(await readFile(ingressRuntimePath, "utf8"));
    return normalizeIngressRuntime(payload);
  } catch (error) {
    if (error?.code === "ENOENT") {
      throw new Error(
        `Missing public workbench runtime profile: ${ingressRuntimePath}. Run npm.cmd run bootstrap:workbench once.`,
      );
    }
    throw error;
  }
}

export async function writePublicWorkbenchIngressRuntime(summary, tunnelToken) {
  const runtime = normalizeIngressRuntime({
    hostname: summary?.hostname,
    localUrl: summary?.localUrl,
    tunnel: summary?.tunnel,
    tunnelToken,
    generatedAt: new Date().toISOString(),
  });

  await mkdir(ingressRuntimeDir, { recursive: true });
  await writeFile(ingressRuntimePath, `${JSON.stringify(runtime, null, 2)}\n`, "utf8");
  return runtime;
}

export function sanitizePublicWorkbenchIngressRuntime(runtime) {
  return {
    ...runtime,
    tunnelToken: maskSecret(runtime?.tunnelToken ?? ""),
  };
}

function normalizeIngressRuntime(payload) {
  const hostname = String(payload?.hostname ?? cloudflareConfig.publicWorkbench.hostname).trim();
  const localUrl = String(payload?.localUrl ?? cloudflareConfig.publicWorkbench.localUrl).trim();
  const tunnelId = String(payload?.tunnel?.id ?? "").trim();
  const tunnelName = String(payload?.tunnel?.name ?? "").trim();
  const tunnelToken = String(payload?.tunnelToken ?? "").trim();
  const generatedAt = String(payload?.generatedAt ?? "").trim();

  if (!hostname) {
    throw new Error("Missing public workbench hostname in runtime profile.");
  }
  if (!localUrl) {
    throw new Error("Missing public workbench localUrl in runtime profile.");
  }
  if (!tunnelId) {
    throw new Error("Missing public workbench tunnel id in runtime profile.");
  }
  if (!tunnelName) {
    throw new Error("Missing public workbench tunnel name in runtime profile.");
  }
  if (!tunnelToken) {
    throw new Error("Missing public workbench tunnel token in runtime profile.");
  }

  return {
    hostname,
    localUrl,
    tunnel: {
      id: tunnelId,
      name: tunnelName,
    },
    tunnelToken,
    generatedAt,
  };
}

function maskSecret(secret) {
  const value = String(secret ?? "");
  if (!value) {
    return "";
  }
  if (value.length <= 8) {
    return "*".repeat(value.length);
  }
  return `${value.slice(0, 4)}...${value.slice(-4)}`;
}
