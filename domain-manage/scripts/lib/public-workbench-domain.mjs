import { cloudflareConfig } from "../../config/cloudflare.mjs";
import { CloudflareApiError } from "./cloudflare-api.mjs";

const FALLBACK_TUNNEL_SERVICE = "http_status:404";

export async function ensurePublicWorkbenchDomain(client) {
  const { accountId, zoneId, publicWorkbench } = cloudflareConfig;
  const tunnel = await ensureTunnel(client, accountId, publicWorkbench);
  await ensureTunnelConfiguration(client, accountId, tunnel.id, publicWorkbench);
  const dnsRecord = await ensureTunnelDnsRecord(client, zoneId, publicWorkbench.hostname, tunnel.id);
  let organization = null;
  let identityProvider = null;
  let application = null;
  let policy = null;

  if (publicWorkbench.access?.enabled) {
    organization = await ensureAccessOrganization(client, accountId, publicWorkbench.access);
    identityProvider = await ensureIdentityProvider(client, accountId, publicWorkbench.access);
    application = await ensureAccessApplication(
      client,
      zoneId,
      publicWorkbench.hostname,
      publicWorkbench.access,
      identityProvider.id,
    );
    policy = await ensureAccessPolicy(
      client,
      zoneId,
      application.id,
      publicWorkbench.access,
    );
  } else {
    await deleteAccessApplication(
      client,
      zoneId,
      publicWorkbench.hostname,
      publicWorkbench.access,
    );
  }

  return {
    hostname: publicWorkbench.hostname,
    localUrl: publicWorkbench.localUrl,
    organization,
    identityProvider,
    tunnel,
    dnsRecord,
    application,
    policy,
  };
}

export async function getPublicWorkbenchTunnelToken(client, tunnelId) {
  const result = await client.request(
    `/accounts/${cloudflareConfig.accountId}/cfd_tunnel/${tunnelId}/token`,
  );
  const token = typeof result === "string" ? result : result?.token ?? "";
  if (!token) {
    throw new Error(`Missing tunnel token for tunnel ${tunnelId}.`);
  }
  return token;
}

async function ensureAccessOrganization(client, accountId, accessConfig) {
  const desired = {
    name: accessConfig.organizationName,
    auth_domain: accessConfig.authDomain,
    session_duration: accessConfig.sessionDuration,
  };
  const existing = await requestOrNull(
    client,
    `/accounts/${accountId}/access/organizations`,
  );

  if (!existing) {
    const created = await client.request(
      `/accounts/${accountId}/access/organizations`,
      {
        method: "POST",
        body: desired,
      },
    );
    return normalizeOrganization(created);
  }

  if (
    existing.name !== desired.name ||
    existing.auth_domain !== desired.auth_domain ||
    existing.session_duration !== desired.session_duration
  ) {
    const updated = await client.request(
      `/accounts/${accountId}/access/organizations`,
      {
        method: "PUT",
        body: desired,
      },
    );
    return normalizeOrganization(updated);
  }

  return normalizeOrganization(existing);
}

async function ensureIdentityProvider(client, accountId, accessConfig) {
  const providers = await listCollection(
    client,
    `/accounts/${accountId}/access/identity_providers`,
  );
  const existing = providers.find(
    (provider) => provider.name === accessConfig.identityProviderName,
  );
  const desired = {
    name: accessConfig.identityProviderName,
    type: "onetimepin",
    config: {},
  };

  if (!existing) {
    const created = await client.request(
      `/accounts/${accountId}/access/identity_providers`,
      {
        method: "POST",
        body: desired,
      },
    );
    return normalizeIdentityProvider(created);
  }

  if (existing.type !== desired.type || existing.name !== desired.name) {
    const updated = await client.request(
      `/accounts/${accountId}/access/identity_providers/${existing.id}`,
      {
        method: "PUT",
        body: desired,
      },
    );
    return normalizeIdentityProvider(updated);
  }

  return normalizeIdentityProvider(existing);
}

async function ensureTunnel(client, accountId, publicWorkbenchConfig) {
  const tunnels = await listCollection(client, `/accounts/${accountId}/cfd_tunnel`, {
    query: {
      per_page: 100,
      is_deleted: false,
    },
  });
  const existing = tunnels.find((tunnel) => tunnel.name === publicWorkbenchConfig.tunnelName);

  if (existing) {
    return normalizeTunnel(existing);
  }

  const created = await client.request(`/accounts/${accountId}/cfd_tunnel`, {
    method: "POST",
    body: {
      name: publicWorkbenchConfig.tunnelName,
      config_src: "cloudflare",
    },
  });

  return normalizeTunnel(created);
}

async function ensureTunnelConfiguration(client, accountId, tunnelId, publicWorkbenchConfig) {
  const desired = {
    config: {
      ingress: [
        {
          hostname: publicWorkbenchConfig.hostname,
          service: publicWorkbenchConfig.localUrl,
        },
        {
          service: FALLBACK_TUNNEL_SERVICE,
        },
      ],
    },
  };

  await client.request(
    `/accounts/${accountId}/cfd_tunnel/${tunnelId}/configurations`,
    {
      method: "PUT",
      body: desired,
    },
  );
}

async function ensureTunnelDnsRecord(client, zoneId, hostname, tunnelId) {
  const target = `${tunnelId}.cfargotunnel.com`;
  const records = await listCollection(client, `/zones/${zoneId}/dns_records`, {
    query: {
      per_page: 100,
      name: hostname,
      type: "CNAME",
    },
  });

  let retainedRecord = null;
  for (const record of records) {
    const isMatch = record.type === "CNAME" && record.name === hostname;
    const isDesiredTarget = record.content === target;

    if (isMatch && isDesiredTarget) {
      retainedRecord = record;
      continue;
    }

    if (!record.meta?.read_only) {
      await client.request(`/zones/${zoneId}/dns_records/${record.id}`, {
        method: "DELETE",
      });
    }
  }

  if (!retainedRecord) {
    retainedRecord = await client.request(`/zones/${zoneId}/dns_records`, {
      method: "POST",
      body: {
        type: "CNAME",
        name: hostname,
        content: target,
        proxied: true,
      },
    });
    return normalizeDnsRecord(retainedRecord);
  }

  if (!retainedRecord.meta?.read_only && retainedRecord.proxied !== true) {
    retainedRecord = await client.request(
      `/zones/${zoneId}/dns_records/${retainedRecord.id}`,
      {
        method: "PUT",
        body: {
          type: "CNAME",
          name: hostname,
          content: target,
          proxied: true,
        },
      },
    );
  }

  return normalizeDnsRecord(retainedRecord);
}

async function ensureAccessApplication(client, zoneId, hostname, accessConfig, identityProviderId) {
  const applications = await listCollection(client, `/zones/${zoneId}/access/apps`, {
    query: {
      per_page: 100,
    },
  });
  const existing = applications.find(
    (application) => application.domain === hostname || application.name === accessConfig.applicationName,
  );
  const desired = {
    name: accessConfig.applicationName,
    type: "self_hosted",
    domain: hostname,
    session_duration: accessConfig.sessionDuration,
    allowed_idps: [identityProviderId],
    auto_redirect_to_identity: true,
    app_launcher_visible: false,
  };

  if (!existing) {
    const created = await client.request(`/zones/${zoneId}/access/apps`, {
      method: "POST",
      body: desired,
    });
    return normalizeAccessApplication(created);
  }

  if (isSameAccessApplication(existing, desired)) {
    return normalizeAccessApplication(existing);
  }

  const updated = await client.request(`/zones/${zoneId}/access/apps/${existing.id}`, {
    method: "PUT",
    body: desired,
  });
  return normalizeAccessApplication(updated);
}

async function deleteAccessApplication(client, zoneId, hostname, accessConfig) {
  const applications = await listCollection(client, `/zones/${zoneId}/access/apps`, {
    query: {
      per_page: 100,
    },
  });

  const targets = applications.filter(
    (application) => application.domain === hostname || application.name === accessConfig.applicationName,
  );

  for (const application of targets) {
    await client.request(`/zones/${zoneId}/access/apps/${application.id}`, {
      method: "DELETE",
    });
  }
}

async function ensureAccessPolicy(client, zoneId, applicationId, accessConfig) {
  const policies = await listCollection(
    client,
    `/zones/${zoneId}/access/apps/${applicationId}/policies`,
    {
      query: {
        per_page: 100,
      },
    },
  );
  const existing = policies.find((policy) => policy.name === accessConfig.policyName);
  const desired = {
    name: accessConfig.policyName,
    precedence: 1,
    decision: "allow",
    include: [{ everyone: {} }],
    exclude: [],
    require: [],
    session_duration: accessConfig.sessionDuration,
  };

  if (!existing) {
    const created = await client.request(
      `/zones/${zoneId}/access/apps/${applicationId}/policies`,
      {
        method: "POST",
        body: desired,
      },
    );
    return normalizeAccessPolicy(created);
  }

  if (isSameAccessPolicy(existing, desired)) {
    return normalizeAccessPolicy(existing);
  }

  const updated = await client.request(
    `/zones/${zoneId}/access/apps/${applicationId}/policies/${existing.id}`,
    {
      method: "PUT",
      body: desired,
    },
  );
  return normalizeAccessPolicy(updated);
}

async function listCollection(client, path, options = {}) {
  const result = await client.request(path, options);
  return Array.isArray(result) ? result : [];
}

async function requestOrNull(client, path, options = {}) {
  try {
    return await client.request(path, options);
  } catch (error) {
    if (error instanceof CloudflareApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

function normalizeOrganization(organization) {
  return {
    name: organization.name,
    authDomain: organization.auth_domain,
    sessionDuration: organization.session_duration,
  };
}

function normalizeIdentityProvider(provider) {
  return {
    id: provider.id,
    name: provider.name,
    type: provider.type,
  };
}

function normalizeTunnel(tunnel) {
  return {
    id: tunnel.id,
    name: tunnel.name,
  };
}

function normalizeDnsRecord(record) {
  return {
    id: record.id,
    hostname: record.name,
    target: record.content,
    proxied: Boolean(record.proxied),
  };
}

function normalizeAccessApplication(application) {
  return {
    id: application.id,
    name: application.name,
    domain: application.domain,
    aud: application.aud,
  };
}

function normalizeAccessPolicy(policy) {
  return {
    id: policy.id,
    name: policy.name,
    precedence: policy.precedence,
    decision: policy.decision,
  };
}

function isSameAccessApplication(existing, desired) {
  return (
    existing.name === desired.name &&
    existing.type === desired.type &&
    existing.domain === desired.domain &&
    existing.session_duration === desired.session_duration &&
    Boolean(existing.auto_redirect_to_identity) === desired.auto_redirect_to_identity &&
    Boolean(existing.app_launcher_visible) === desired.app_launcher_visible &&
    JSON.stringify(toSortedStrings(existing.allowed_idps)) ===
      JSON.stringify(toSortedStrings(desired.allowed_idps))
  );
}

function isSameAccessPolicy(existing, desired) {
  return (
    existing.name === desired.name &&
    Number(existing.precedence) === desired.precedence &&
    existing.decision === desired.decision &&
    existing.session_duration === desired.session_duration &&
    JSON.stringify(existing.include ?? []) === JSON.stringify(desired.include) &&
    JSON.stringify(existing.exclude ?? []) === JSON.stringify(desired.exclude) &&
    JSON.stringify(existing.require ?? []) === JSON.stringify(desired.require)
  );
}

function toSortedStrings(values) {
  return [...(values ?? [])].map(String).sort();
}
