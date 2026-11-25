// DCT dashboard — Run detail / evidence pack screen.
const DSr = window.DCTDesignSystem_a2ec41;

function CheckRow({ check }) {
  const pass = check.status === 'approved';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '10px 14px', borderTop: '1px solid var(--border-hairline)' }}>
      <span style={{ display: 'flex', color: pass ? 'var(--accent-green)' : 'var(--accent-red)' }}>
        <DSr.Icon name={pass ? 'circle-check' : 'circle-x'} size={16} />
      </span>
      <span style={{ flex: 1, fontSize: 'var(--text-sm)', fontWeight: 500, color: 'var(--text-1)' }}>{check.name}</span>
      <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-3)' }}>{check.detail}</span>
      <code style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--text-3)', width: 56, textAlign: 'right' }}>{check.time}</code>
    </div>
  );
}

function RunDetailScreen({ run, onDecision }) {
  const d = window.DCT_DATA;
  const [tab, setTab] = React.useState('checks');
  const [confirm, setConfirm] = React.useState(null); // 'approve' | 'reject'
  const decided = run.status === 'approved' || run.status === 'rejected';
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-5)', animation: 'dct-fade-in var(--duration-slow) var(--ease-out)' }}>
      <DSr.Card
        title={run.task}
        subtitle={`Agent ${run.agent} · started ${run.age} ago`}
        action={
          <DSr.Badge status={run.status === 'pending' ? 'pending' : run.status} dot={run.status === 'running'} pulse={run.status === 'running'}>
            {run.status === 'pending' ? 'Needs review' : run.status}
          </DSr.Badge>
        }
      >
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }}>
          <DSr.Tag icon="box" mono>{run.repo}</DSr.Tag>
          <DSr.Tag icon="git-branch" mono>{run.branch}</DSr.Tag>
          <DSr.Tag icon="shield" mono>strict-prod</DSr.Tag>
          <DSr.Tag icon="git-commit-horizontal" mono>sha:1f8c2ea</DSr.Tag>
          <div style={{ flex: 1 }}></div>
          <DSr.Tooltip content="Copy run ID"><DSr.IconButton icon="copy" label="Copy run ID" size="sm" /></DSr.Tooltip>
          <DSr.Tooltip content="Open branch"><DSr.IconButton icon="external-link" label="Open branch" size="sm" /></DSr.Tooltip>
        </div>
      </DSr.Card>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 'var(--space-5)', alignItems: 'start' }}>
        <DSr.Card padding="0 var(--space-5) var(--space-3)">
          <DSr.Tabs
            tabs={[
              { value: 'checks', label: 'Checks', count: d.checks.length },
              { value: 'artifacts', label: 'Artifacts', count: d.artifacts.length },
              { value: 'log', label: 'Log' },
            ]}
            value={tab}
            onChange={setTab}
          />
          {tab === 'checks' ? (
            <div style={{ margin: '0 -14px' }}>{d.checks.map((c) => <CheckRow key={c.name} check={c} />)}</div>
          ) : null}
          {tab === 'artifacts' ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', paddingTop: 'var(--space-4)' }}>
              {d.artifacts.map((a) => (
                <div key={a.name} style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '10px 12px', background: 'var(--surface-glass-2)', border: '1px solid var(--border-hairline)', borderRadius: 'var(--radius-md)' }}>
                  <span style={{ color: 'var(--text-2)' }}><DSr.Icon name={a.icon} size={16} /></span>
                  <code style={{ flex: 1, fontFamily: 'var(--font-mono)', fontSize: 'var(--text-sm)', color: 'var(--text-1)' }}>{a.name}</code>
                  <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-3)' }}>{a.size}</span>
                  <DSr.IconButton icon="external-link" label="Open artifact" variant="ghost" size="sm" />
                </div>
              ))}
            </div>
          ) : null}
          {tab === 'log' ? (
            <pre style={{ margin: 'var(--space-4) 0 0', padding: '14px 16px', background: 'var(--bg-inset)', border: '1px solid var(--border-hairline)', borderRadius: 'var(--radius-md)', fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', lineHeight: 1.8, color: 'var(--text-2)', overflowX: 'auto' }}>{d.log.join('\n')}</pre>
          ) : null}
        </DSr.Card>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-5)' }}>
          <DSr.Card title="Evidence summary">
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-5)' }}>
              <DSr.Stat label="Checks" value={run.checks} accent={run.status === 'rejected' ? 'red' : 'green'} />
              <DSr.Stat label="Files changed" value="42" accent="neutral" detail="+1,180 −642" />
            </div>
          </DSr.Card>
          <DSr.Card title="Review decision" subtitle="Human gate — final call">
            {decided ? (
              <DSr.Toast
                kind={run.status === 'approved' ? 'success' : 'error'}
                title={run.status === 'approved' ? 'Approved' : 'Rejected'}
                description={run.status === 'approved' ? 'Merged to main.' : 'Returned to queue with notes.'}
                style={{ width: '100%' }}
              />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <DSr.Button variant="success" icon="check" onClick={() => setConfirm('approve')}>Approve &amp; merge</DSr.Button>
                <DSr.Button variant="danger" icon="x" onClick={() => setConfirm('reject')}>Reject</DSr.Button>
                <DSr.Button variant="ghost" size="sm" icon="clock">Request changes</DSr.Button>
              </div>
            )}
          </DSr.Card>
        </div>
      </div>

      <DSr.Dialog
        open={confirm !== null}
        onClose={() => setConfirm(null)}
        title={confirm === 'approve' ? 'Approve this run?' : 'Reject this run?'}
        subtitle={`${run.id} · ${run.repo}`}
        footer={
          <React.Fragment>
            <DSr.Button variant="ghost" onClick={() => setConfirm(null)}>Cancel</DSr.Button>
            {confirm === 'approve'
              ? <DSr.Button variant="success" icon="check" onClick={() => { onDecision(run, 'approved'); setConfirm(null); }}>Approve &amp; merge</DSr.Button>
              : <DSr.Button variant="danger" icon="x" onClick={() => { onDecision(run, 'rejected'); setConfirm(null); }}>Reject run</DSr.Button>}
          </React.Fragment>
        }
      >
        {confirm === 'approve'
          ? `All ${run.checks} checks passed under strict-prod. Approving merges ${run.branch} to main and closes the task.`
          : 'The agent’s changes will be discarded and the task returned to the queue. This can’t be undone.'}
      </DSr.Dialog>
    </div>
  );
}

Object.assign(window, { RunDetailScreen });
