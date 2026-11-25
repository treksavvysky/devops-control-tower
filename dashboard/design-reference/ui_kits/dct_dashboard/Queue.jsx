// DCT dashboard — Review queue screen.
const DSq = window.DCTDesignSystem_a2ec41;

function QueueScreen({ runs, onOpenRun }) {
  const pending = runs.filter((r) => r.status === 'pending');
  const rest = runs.filter((r) => r.status !== 'pending' && r.status !== 'running');
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-5)', maxWidth: 860, animation: 'dct-fade-in var(--duration-slow) var(--ease-out)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <DSq.Select options={[{ value: 'all', label: 'All repos' }, { value: 'core-api', label: 'core-api' }, { value: 'edge-proxy', label: 'edge-proxy' }]} style={{ width: 160 }} />
        <DSq.Tag icon="funnel">policy: strict-prod</DSq.Tag>
        <div style={{ flex: 1 }}></div>
        <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-3)' }}>{pending.length} awaiting review</span>
      </div>
      {pending.map((run) => (
        <DSq.Card key={run.id} interactive onClick={() => onOpenRun(run)}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-4)' }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 38, height: 38, borderRadius: 11, flexShrink: 0, background: 'var(--tint-amber)', border: '1px solid var(--line-amber)', color: 'var(--accent-amber)' }}>
              <DSq.Icon name="eye" size={17} />
            </span>
            <div style={{ flex: 1, minWidth: 0, lineHeight: 1.4 }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '10px' }}>
                <span style={{ fontSize: 'var(--text-md)', fontWeight: 600, color: 'var(--text-1)' }}>{run.task}</span>
                <code style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--text-3)' }}>{run.id}</code>
              </div>
              <div style={{ display: 'flex', gap: '8px', marginTop: 6 }}>
                <DSq.Tag icon="box" mono>{run.repo}</DSq.Tag>
                <DSq.Tag icon="git-branch" mono>{run.branch}</DSq.Tag>
                <DSq.Tag icon="list-checks">{run.checks} checks</DSq.Tag>
              </div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '8px', flexShrink: 0 }}>
              <DSq.Badge status="pending">Needs review</DSq.Badge>
              <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-3)' }}>waiting {run.age}</span>
            </div>
          </div>
        </DSq.Card>
      ))}
      <div style={{ borderTop: '1px solid var(--border-hairline)', paddingTop: 'var(--space-4)', display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
        <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 'var(--tracking-label)', color: 'var(--text-3)' }}>Recently decided</span>
        {rest.map((run) => (
          <div key={run.id} onClick={() => onOpenRun(run)} style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '10px 14px', background: 'var(--surface-glass-2)', border: '1px solid var(--border-hairline)', borderRadius: 'var(--radius-md)', cursor: 'pointer' }}>
            <span style={{ display: 'flex', color: run.status === 'approved' ? 'var(--accent-green)' : 'var(--accent-red)' }}>
              <DSq.Icon name={run.status === 'approved' ? 'circle-check' : 'circle-x'} size={16} />
            </span>
            <span style={{ flex: 1, fontSize: 'var(--text-sm)', color: 'var(--text-2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{run.task}</span>
            <DSq.Badge status={run.status}>{run.status}</DSq.Badge>
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-3)', width: 32, textAlign: 'right' }}>{run.age}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

Object.assign(window, { QueueScreen });
