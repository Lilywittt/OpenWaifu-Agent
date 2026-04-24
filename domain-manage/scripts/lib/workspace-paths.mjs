import { access } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const domainManageDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
export const workspaceDir = path.resolve(domainManageDir, "..");
export const openwaifuAgentDir = path.join(workspaceDir, "openwaifu-agent");

export async function assertOpenwaifuAgentWorkspace() {
  const requiredPaths = [
    path.join(openwaifuAgentDir, "run_public_workbench.py"),
    path.join(openwaifuAgentDir, "docs", "public_workbench.md"),
  ];

  for (const requiredPath of requiredPaths) {
    await access(requiredPath);
  }

  return {
    domainManageDir,
    workspaceDir,
    openwaifuAgentDir,
  };
}
