import { createCloudflareClient } from "./lib/cloudflare-api.mjs";
import {
  ensurePublicWorkbenchDomain,
  getPublicWorkbenchTunnelToken,
} from "./lib/public-workbench-domain.mjs";
import {
  getPublicWorkbenchIngressRuntimePath,
  sanitizePublicWorkbenchIngressRuntime,
  writePublicWorkbenchIngressRuntime,
} from "./lib/public-workbench-runtime.mjs";
import { assertOpenwaifuAgentWorkspace } from "./lib/workspace-paths.mjs";

await assertOpenwaifuAgentWorkspace();

const client = createCloudflareClient();
const summary = await ensurePublicWorkbenchDomain(client);
const tunnelToken = await getPublicWorkbenchTunnelToken(client, summary.tunnel.id);
const runtime = await writePublicWorkbenchIngressRuntime(summary, tunnelToken);

console.log(
  JSON.stringify(
    {
      ...summary,
      runtime: sanitizePublicWorkbenchIngressRuntime(runtime),
      runtimePath: getPublicWorkbenchIngressRuntimePath(),
    },
    null,
    2,
  ),
);
