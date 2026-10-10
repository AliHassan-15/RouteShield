// JSON is a YAML subset: the workflow needs no extra syntax-validation dependency.
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const root = new URL('../', import.meta.url);
const workflow = JSON.parse(readFileSync(new URL('.github/workflows/ci.yml', root), 'utf8'));
assert.equal(workflow.permissions.contents, 'read');
assert.ok(workflow.on.push && workflow.on.pull_request);
const steps = workflow.jobs.foundation.steps;
for (const command of ['setup', 'lint', 'typecheck', 'test', 'build', 'ci-check']) {
  assert.ok(steps.some(step => step.run === 'python "./dev.py" ' + command));
}
for (const path of ['backend/requirements.lock', 'frontend/package-lock.json', 'dev.py']) {
  assert.ok(existsSync(fileURLToPath(new URL(path, root))), path);
}
assert.equal(workflow.jobs.foundation['runs-on'], 'ubuntu-latest');
assert.equal(workflow.jobs.foundation.defaults.run['working-directory'], 'Projects New/RouteShield');
assert.equal(steps[0].with.path, 'Projects New/RouteShield');
console.log('CI YAML syntax and foundation command/path checks passed.');
