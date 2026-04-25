import { readFileSync } from "node:fs";
import path from "node:path";

import { domainManageDir } from "./workspace-paths.mjs";

const domainManageEnvPath = path.join(domainManageDir, ".env.local");

let loaded = false;

export function getDomainManageEnvPath() {
  return domainManageEnvPath;
}

export function loadDomainManageEnv() {
  if (loaded) {
    return domainManageEnvPath;
  }

  try {
    const source = readFileSync(domainManageEnvPath, "utf8");
    const parsed = parseEnvDocument(source);
    for (const [key, value] of Object.entries(parsed)) {
      if (!process.env[key]) {
        process.env[key] = value;
      }
    }
  } catch (error) {
    if (error?.code !== "ENOENT") {
      throw error;
    }
  }

  loaded = true;
  return domainManageEnvPath;
}

export function getCloudflareApiToken() {
  loadDomainManageEnv();
  const apiToken = String(process.env.CLOUDFLARE_API_TOKEN ?? "").trim();
  if (!apiToken) {
    throw new Error(
      `Missing CLOUDFLARE_API_TOKEN. Put it in ${domainManageEnvPath} or the current shell environment.`,
    );
  }
  return apiToken;
}

function parseEnvDocument(source) {
  const result = {};
  for (const rawLine of source.split(/\r?\n/u)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) {
      continue;
    }

    const normalized = line.startsWith("export ") ? line.slice("export ".length).trim() : line;
    const separatorIndex = normalized.indexOf("=");
    if (separatorIndex <= 0) {
      continue;
    }

    const key = normalized.slice(0, separatorIndex).trim();
    if (!key) {
      continue;
    }

    const rawValue = normalized.slice(separatorIndex + 1).trim();
    result[key] = unquote(rawValue);
  }

  return result;
}

function unquote(value) {
  if (value.length >= 2) {
    const startsWithDoubleQuote = value.startsWith("\"") && value.endsWith("\"");
    const startsWithSingleQuote = value.startsWith("'") && value.endsWith("'");
    if (startsWithDoubleQuote || startsWithSingleQuote) {
      return value.slice(1, -1);
    }
  }
  return value;
}
