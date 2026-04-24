import { createCloudflareClient } from "./lib/cloudflare-api.mjs";
import {
  ensurePublicWorkbenchDomain,
  getPublicWorkbenchTunnelToken,
} from "./lib/public-workbench-domain.mjs";
import { assertOpenwaifuAgentWorkspace } from "./lib/workspace-paths.mjs";

await assertOpenwaifuAgentWorkspace();

const client = createCloudflareClient();
const summary = await ensurePublicWorkbenchDomain(client);
const token = await getPublicWorkbenchTunnelToken(client, summary.tunnel.id);

console.log(
  JSON.stringify(
    {
      ...summary,
      tunnelToken: token,
    },
    null,
    2,
  ),
);
