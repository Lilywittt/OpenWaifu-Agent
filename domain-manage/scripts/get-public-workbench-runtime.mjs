import { createCloudflareClient } from "./lib/cloudflare-api.mjs";
import {
  ensurePublicWorkbenchDomain,
  getPublicWorkbenchTunnelToken,
} from "./lib/public-workbench-domain.mjs";
import {
  getPublicWorkbenchIngressRuntimePath,
  loadPublicWorkbenchIngressRuntime,
  sanitizePublicWorkbenchIngressRuntime,
  writePublicWorkbenchIngressRuntime,
} from "./lib/public-workbench-runtime.mjs";
import { assertOpenwaifuAgentWorkspace } from "./lib/workspace-paths.mjs";

await assertOpenwaifuAgentWorkspace();

const args = new Set(process.argv.slice(2));
const shouldRefresh = args.has("--refresh");

let runtime;
if (shouldRefresh) {
  const client = createCloudflareClient();
  const summary = await ensurePublicWorkbenchDomain(client);
  const tunnelToken = await getPublicWorkbenchTunnelToken(client, summary.tunnel.id);
  runtime = await writePublicWorkbenchIngressRuntime(summary, tunnelToken);
} else {
  runtime = await loadPublicWorkbenchIngressRuntime();
}

console.log(
  JSON.stringify(
    {
      ...runtime,
      tunnelToken: sanitizePublicWorkbenchIngressRuntime(runtime).tunnelToken,
      runtimePath: getPublicWorkbenchIngressRuntimePath(),
    },
    null,
    2,
  ),
);
