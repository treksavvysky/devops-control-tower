// DCT dashboard — demo data. Plain script; exposes window.DCT_DATA.
window.DCT_DATA = {
  stats: [
    { label: 'Active runs', value: '12', accent: 'blue' },
    { label: 'Pass rate (7d)', value: '98.2%', accent: 'green' },
    { label: 'Pending review', value: '4', accent: 'amber', detail: 'oldest 14m' },
    { label: 'Rejected today', value: '1', accent: 'red' },
  ],
  agents: [
    { name: 'atlas-01', model: 'claude-4.5-opus', status: 'running', task: 'Migrate billing cron to queue worker', uptime: '3h 12m' },
    { name: 'atlas-02', model: 'claude-4.5-opus', status: 'running', task: 'Fix flaky auth integration tests', uptime: '1h 48m' },
    { name: 'vega-01', model: 'claude-4.5-sonnet', status: 'running', task: 'Bump TLS ciphers on edge proxy', uptime: '22m' },
    { name: 'vega-02', model: 'claude-4.5-sonnet', status: 'neutral', task: 'Idle — awaiting task', uptime: '—' },
  ],
  runs: [
    { id: 'run_8f3ka92', task: 'Migrate billing cron to queue worker', repo: 'core-api', branch: 'feat/billing-queue', status: 'pending', checks: '12/12', agent: 'atlas-01', age: '14m' },
    { id: 'run_7cd21xe', task: 'Fix flaky auth integration tests', repo: 'core-api', branch: 'fix/auth-flake', status: 'running', checks: '8/12', agent: 'atlas-02', age: '2m' },
    { id: 'run_6ba99qt', task: 'Bump TLS ciphers on edge proxy', repo: 'edge-proxy', branch: 'chore/tls-bump', status: 'running', checks: '3/9', agent: 'vega-01', age: '5m' },
    { id: 'run_5fe10pl', task: 'Add rate-limit headers to public API', repo: 'core-api', branch: 'feat/rl-headers', status: 'pending', checks: '9/9', agent: 'vega-02', age: '41m' },
    { id: 'run_4dd83mn', task: 'Rotate stale feature flags', repo: 'web-app', branch: 'chore/flag-cleanup', status: 'approved', checks: '11/11', agent: 'atlas-01', age: '1h' },
    { id: 'run_3cc71zu', task: 'Patch CVE-2026-1183 in image pipeline', repo: 'media-svc', branch: 'fix/cve-1183', status: 'rejected', checks: '7/10', agent: 'vega-01', age: '2h' },
  ],
  checks: [
    { name: 'Unit tests', detail: '842 passed', status: 'approved', time: '48s' },
    { name: 'Integration tests', detail: '96 passed', status: 'approved', time: '3m 12s' },
    { name: 'Type check', detail: 'tsc --strict', status: 'approved', time: '21s' },
    { name: 'Lint', detail: '0 warnings', status: 'approved', time: '9s' },
    { name: 'Policy: no schema drops', detail: 'strict-prod', status: 'approved', time: '2s' },
    { name: 'Policy: secrets scan', detail: '0 findings', status: 'approved', time: '11s' },
    { name: 'Diff coverage', detail: '94% (min 80%)', status: 'approved', time: '14s' },
    { name: 'Canary deploy', detail: 'error rate +0.0%', status: 'approved', time: '6m 40s' },
  ],
  artifacts: [
    { name: 'diff.patch', size: '18 KB', icon: 'file-check' },
    { name: 'test-report.junit.xml', size: '212 KB', icon: 'list-checks' },
    { name: 'canary-metrics.json', size: '9 KB', icon: 'activity' },
  ],
  log: [
    '16:02:11  policy   validate task against strict-prod … ok',
    '16:02:14  agent    atlas-01 claimed task tk_2211',
    '16:04:52  exec     branch feat/billing-queue created',
    '16:31:07  exec     42 files changed, +1,180 −642',
    '16:31:40  checks   8 checks queued',
    '16:42:19  checks   all checks passed (12/12)',
    '16:42:20  gate     awaiting human review',
  ],
};
