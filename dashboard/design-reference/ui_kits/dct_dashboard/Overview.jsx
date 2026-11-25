// DCT dashboard — Overview screen.
const DSo = window.DCTDesignSystem_a2ec41;

const RUN_STATUS_LABEL = { running: 'Running', pending: 'Needs review', approved: 'Approved', rejected: 'Rejected' };

function RunRow({ run, onOpen }) {
  const [hover, setHover] = React.useState(false);
  return (
    <tr
      onClick={() => onOpen(run)}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{ cursor: 'pointer', background: hover ? 'rgba(255,255,255,0.03)' : 'transparent', transition: 'background var(--duration-fast) var(--ease-out)' }}
    >
      <td style={{ padding: '10px 12px', borderTop: '1px solid var(--border-hairline)' }}>
        <code style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-sm)', color: 'var(--text-1)' }}>{run.id}</code>
      </td>
      <td style={{ padding: '10px 12px', borderTop: '1px solid var(--border-hairline)', maxWidth: 280 }}>
        <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{run.task}</div>
      </td>
      <td style={{ padding: '10px 12px', borderTop: '1px solid var(--border-hairline)' }}>
        <DSo.Tag icon="git-branch" mono>{run.branch}</DSo.Tag>
      </td>
      <td style={{ padding: '10px 12px', borderTop: '1px solid var(--border-hairline)', fontFamily: 'var(--font-mono)', fontSize: 'var(--text-sm)', color: run.status === 'rejected' ? 'var(--accent-red)' : 'var(--text-2)' }}>{run.checks}</td>
      <td style={{ padding: '10px 12px', borderTop: '1px solid var(--border-hairline)' }}>
        <DSo.Badge status={run.status === 'pending' ? 'pending' : run.status} dot={run.status === 'running'} pulse={run.status === 'running'}>
          {RUN_STATUS_LABEL[run.status]}
        </DSo.Badge>
      </td>
      <td style={{ padding: '10px 12px', borderTop: '1px solid var(--border-hairline)', fontSize: 'var(--text-sm)', color: 'var(--text-3)', textAlign: 'right' }}>{run.age}</td>
    </tr>
  );
}

function OverviewScreen({ onOpenRun, onNav }) {
  const d = window.DCT_DATA;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-5)', animation: 'dct-fade-in var(--duration-slow) var(--ease-out)' }}>
      <DSo.Card>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--space-6)' }}>
          {d.stats.map((s) => <DSo.Stat key={s.label} label={s.label} value={s.value} accent={s.accent} detail={s.detail} />)}
        </div>
      </DSo.Card>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 'var(--space-5)', alignItems: 'start' }}>
        <DSo.Card title="Recent runs" subtitle="Streaming from all agents" action={<DSo.Button variant="secondary" size="sm" icon="eye" onClick={() => onNav('queue')}>Review queue</DSo.Button>} padding="var(--space-3) 0 0">
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Run', 'Task', 'Branch', 'Checks', 'Status', 'Age'].map((h, i) => (
                  <th key={h} style={{ padding: '4px 12px 10px', textAlign: i === 5 ? 'right' : 'left', fontSize: 'var(--text-xs)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 'var(--tracking-label)', color: 'var(--text-3)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {d.runs.map((r) => <RunRow key={r.id} run={r} onOpen={onOpenRun} />)}
            </tbody>
          </table>
        </DSo.Card>
        <DSo.Card title="Active agents" subtitle="3 of 4 running" action={<DSo.Badge status="running" dot pulse>Live</DSo.Badge>}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
            {d.agents.map((a) => (
              <div key={a.name} style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '10px 12px', background: 'var(--surface-glass-2)', border: '1px solid var(--border-hairline)', borderRadius: 'var(--radius-md)' }}>
                <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 30, height: 30, borderRadius: 9, flexShrink: 0, background: a.status === 'running' ? 'var(--tint-blue)' : 'rgba(255,255,255,0.05)', border: `1px solid ${a.status === 'running' ? 'var(--line-blue)' : 'var(--border-hairline)'}`, color: a.status === 'running' ? 'var(--accent-blue)' : 'var(--text-3)' }}>
                  <DSo.Icon name="cpu" size={15} />
                </span>
                <div style={{ flex: 1, minWidth: 0, lineHeight: 1.35 }}>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
                    <code style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-1)' }}>{a.name}</code>
                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-3)' }}>{a.uptime}</span>
                  </div>
                  <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.task}</div>
                </div>
                <span style={{ width: 7, height: 7, borderRadius: '50%', flexShrink: 0, background: a.status === 'running' ? 'var(--accent-blue)' : 'var(--text-3)', animation: a.status === 'running' ? 'dct-pulse 1.6s ease-in-out infinite' : 'none' }}></span>
              </div>
            ))}
          </div>
        </DSo.Card>
      </div>
    </div>
  );
}

Object.assign(window, { OverviewScreen });
