const API_ROOT = "https://api.cloudflare.com/client/v4";

export class CloudflareApiError extends Error {
  constructor(message, payload) {
    super(message);
    this.name = "CloudflareApiError";
    this.payload = payload;
  }
}

export function createCloudflareClient({ apiToken = process.env.CLOUDFLARE_API_TOKEN } = {}) {
  if (!apiToken) {
    throw new Error("Missing CLOUDFLARE_API_TOKEN.");
  }

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

  const details = JSON.stringify(payload?.errors ?? payload, null, 2);
  throw new CloudflareApiError(`Cloudflare API request failed: ${details}`, payload);
}
