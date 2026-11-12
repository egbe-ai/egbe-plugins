const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

module.exports = function connectionHeaders(url, envFile = null) {
  const root = path.resolve(__dirname, '../..');
  const quickstart = path.basename(root).startsWith('egbe-os-') ? 'egbe-os-quickstart' : 'quickstart';
  const helper = path.resolve(root, '..', quickstart, 'scripts/egbe-curl.py');
  if (!fs.existsSync(helper) || (!envFile && !process.env.OS_AGENT_NAME)) return {};
  const args = [helper, '--identity-headers', url];
  if (envFile) args.push('--env-file', envFile);
  const result = spawnSync('python3', args, {
    encoding: 'utf8', maxBuffer: 65536, windowsHide: true,
  });
  if (result.status !== 0) return {};
  try { return JSON.parse(result.stdout); } catch { return {}; }
};
