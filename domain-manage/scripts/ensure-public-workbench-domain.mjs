import { createCloudflareClient } from "./lib/cloudflare-api.mjs";
import { ensurePublicWorkbenchDomain } from "./lib/public-workbench-domain.mjs";
import { assertOpenwaifuAgentWorkspace } from "./lib/workspace-paths.mjs";

await assertOpenwaifuAgentWorkspace();

const client = createCloudflareClient();
const summary = await ensurePublicWorkbenchDomain(client);

console.log(JSON.stringify(summary, null, 2));
