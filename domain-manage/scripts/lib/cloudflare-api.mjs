const API_ROOT = "https://api.cloudflare.com/client/v4";

import { getCloudflareApiToken, getDomainManageEnvPath } from "./domain-manage-env.mjs";

export class CloudflareApiError extends Error {
  constructor(message, payload, status = 0) {
    super(message);
    this.name = "CloudflareApiError";
    this.payload = payload;
    this.status = status;
  }
}

export function createCloudflareClient({ apiToken = getCloudflareApiToken() } = {}) {

  return {
    request(path, options = {}) {
      return requestCloudflare(path, { ...options, apiToken });
    },
  };
}

async function requestCloudflare(
  path,
  {
    apiToken,
    method = "GET",
    query,
    body,
    headers = {},
  } = {},
) {
  const url = new URL(`${API_ROOT}${path}`);
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value === undefined || value === null || value === "") {
      continue;
    }
    url.searchParams.set(key, String(value));
  }

  const requestHeaders = new Headers({
    Authorization: `Bearer ${apiToken}`,
    ...headers,
  });

  let requestBody;
  if (body !== undefined) {
    requestHeaders.set("Content-Type", "application/json");
    requestBody = JSON.stringify(body);
  }

  const response = await fetch(url, {
    method,
    headers: requestHeaders,
    body: requestBody,
  });

  const contentType = response.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (response.ok && (!payload || payload.success !== false)) {
    return payload?.result ?? payload;
  }

  const authFailed =
    response.status === 403 &&
    Array.isArray(payload?.errors) &&
    payload.errors.some((error) => Number(error?.code) === 10000);
  const details = JSON.stringify(payload?.errors ?? payload, null, 2);
  const message = authFailed
    ? `Cloudflare authentication failed. Check CLOUDFLARE_API_TOKEN in ${getDomainManageEnvPath()}.`
    : `Cloudflare API request failed: ${details}`;
  throw new CloudflareApiError(
    message,
    payload,
    response.status,
  );
}
