// DCT dashboard — app shell: sidebar + top bar.
const DS = window.DCTDesignSystem_a2ec41;

function Wordmark() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '4px 8px' }}>
      <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 30, height: 30, borderRadius: 9, background: 'var(--grad-blue)', boxShadow: 'var(--glow-blue)', color: '#fff', fontWeight: 800, fontSize: 12, letterSpacing: '-0.02em', flexShrink: 0 }}>DCT</span>
      <span style={{ fontSize: 14, fontWeight: 700, letterSpacing: 'var(--tracking-tight)', color: 'var(--text-1)', whiteSpace: 'nowrap' }}>Control Tower</span>
    </div>
  );
}

function NavItem({ icon, label, active, badge, onClick }) {
  const [hover, setHover] = React.useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: 'flex', alignItems: 'center', gap: '10px', width: '100%',
        padding: '9px 12px', border: 'none', borderRadius: 'var(--radius-sm)',
        background: active ? 'var(--tint-blue)' : hover ? 'rgba(255,255,255,0.04)' : 'transparent',
        color: active ? 'var(--accent-blue)' : 'var(--text-2)',
        fontFamily: 'var(--font-sans)', fontSize: 'var(--text-sm)',
        fontWeight: active ? 600 : 500, cursor: 'pointer', textAlign: 'left',
        transition: 'background var(--duration-fast) var(--ease-out), color var(--duration-fast) var(--ease-out)',
      }}
    >
      <DS.Icon name={icon} size={16} />
      <span style={{ flex: 1 }}>{label}</span>
      {badge !== undefined ? (
        <span style={{ padding: '1px 8px', borderRadius: 'var(--radius-pill)', background: 'var(--tint-amber)', border: '1px solid var(--line-amber)', color: 'var(--accent-amber)', fontSize: 'var(--text-xs)', fontWeight: 600 }}>{badge}</span>
      ) : null}
    </button>
  );
}

function Sidebar({ screen, onNav }) {
  return (
    <aside style={{
      width: 'var(--sidebar-width)', flexShrink: 0, display: 'flex', flexDirection: 'column', gap: '4px',
      padding: '18px 12px', borderRight: '1px solid var(--border-hairline)',
      background: 'rgba(15, 17, 21, 0.7)', backdropFilter: 'var(--blur-glass)', WebkitBackdropFilter: 'var(--blur-glass)',
    }}>
      <Wordmark />
      <div style={{ height: 18 }}></div>
      <NavItem icon="layout-dashboard" label="Overview" active={screen === 'overview'} onClick={() => onNav('overview')} />
      <NavItem icon="eye" label="Review queue" active={screen === 'queue'} badge={4} onClick={() => onNav('queue')} />
      <NavItem icon="cpu" label="Agents" active={false} onClick={() => onNav('overview')} />
      <NavItem icon="shield" label="Policies" active={false} onClick={() => onNav('overview')} />
      <NavItem icon="history" label="History" active={false} onClick={() => onNav('overview')} />
      <div style={{ flex: 1 }}></div>
      <NavItem icon="settings" label="Settings" active={false} onClick={() => {}} />
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '10px 12px', marginTop: 4, borderTop: '1px solid var(--border-hairline)' }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 28, height: 28, borderRadius: '50%', background: 'var(--surface-glass-2)', border: '1px solid var(--border-strong)', color: 'var(--text-2)' }}>
          <DS.Icon name="user" size={14} />
        </span>
        <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.3 }}>
          <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-1)' }}>M. Reyes</span>
          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-3)' }}>Release operator</span>
        </div>
      </div>
    </aside>
  );
}

function TopBar({ title, crumb, onBack }) {
  return (
    <header style={{ display: 'flex', alignItems: 'center', gap: '16px', padding: '16px 28px', borderBottom: '1px solid var(--border-hairline)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: 1, minWidth: 0 }}>
        {onBack ? <DS.IconButton icon="chevron-right" label="Back" variant="ghost" onClick={onBack} style={{ transform: 'rotate(180deg)' }} /> : null}
        <h1 style={{ margin: 0, fontSize: 'var(--text-xl)', fontWeight: 700, letterSpacing: 'var(--tracking-tight)', background: 'var(--grad-headline)', WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent', whiteSpace: 'nowrap' }}>{title}</h1>
        {crumb ? <code style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-sm)', color: 'var(--text-3)' }}>{crumb}</code> : null}
      </div>
      <div style={{ width: 260 }}>
        <DS.Input icon="search" placeholder="Search runs, agents, tasks" />
      </div>
      <DS.IconButton icon="bell" label="Notifications" />
    </header>
  );
}

Object.assign(window, { Sidebar, TopBar });
