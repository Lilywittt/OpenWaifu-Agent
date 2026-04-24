export const cloudflareConfig = {
  accountId: "ec0c5bcab04268171d57a073a220324f",
  zoneId: "3fd76e41df8c48b01aebf39290b8574e",
  zoneName: "openwaifu-agent.uk",
  homepage: {
    hostname: "openwaifu-agent.uk",
    serviceName: "openwaifu-domain-home",
  },
  publicWorkbench: {
    hostname: "hi.openwaifu-agent.uk",
    localUrl: "http://127.0.0.1:8767",
    tunnelName: "openwaifu-public-workbench",
    access: {
      organizationName: "OpenWaifu-Agent",
      authDomainCandidates: [
        "openwaifu-agent.cloudflareaccess.com",
        "openwaifu-agent-uk.cloudflareaccess.com",
        "openwaifu-agent-public.cloudflareaccess.com",
        "openwaifu-public-workbench.cloudflareaccess.com",
      ],
      identityProviderName: "OpenWaifu-Agent One-Time Pin",
      applicationName: "OpenWaifu-Agent Public Workbench",
      policyName: "OpenWaifu-Agent Public Access",
      sessionDuration: "24h",
    },
  },
};
