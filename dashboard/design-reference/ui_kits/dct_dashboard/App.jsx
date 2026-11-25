// DCT dashboard — root app: nav state, decisions, toasts.
const DSa = window.DCTDesignSystem_a2ec41;

function App() {
  const [screen, setScreen] = React.useState('overview');
  const [runs, setRuns] = React.useState(window.DCT_DATA.runs);
  const [selected, setSelected] = React.useState(null);
  const [toast, setToast] = React.useState(null);

  const openRun = (run) => { setSelected(run); setScreen('run'); };
  const decide = (run, status) => {
    const updated = runs.map((r) => (r.id === run.id ? { ...r, status } : r));
    setRuns(updated);
    setSelected({ ...run, status });
    setToast(status === 'approved'
      ? { kind: 'success', title: 'Run approved', description: `${run.id} merged to main` }
      : { kind: 'error', title: 'Run rejected', description: `${run.id} returned to queue` });
    setTimeout(() => setToast(null), 4000);
  };

  const title = screen === 'overview' ? 'Overview' : screen === 'queue' ? 'Review queue' : 'Evidence pack';

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      <Sidebar screen={screen} onNav={(s) => { setScreen(s); setSelected(null); }} />
      <main style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        <TopBar
          title={title}
          crumb={screen === 'run' && selected ? selected.id : undefined}
          onBack={screen === 'run' ? () => setScreen('queue') : undefined}
        />
        <div style={{ flex: 1, overflowY: 'auto', padding: 'var(--space-6) var(--space-8)' }}>
          {screen === 'overview' ? <OverviewScreen onOpenRun={openRun} onNav={setScreen} /> : null}
          {screen === 'queue' ? <QueueScreen runs={runs} onOpenRun={openRun} /> : null}
          {screen === 'run' && selected ? <RunDetailScreen run={runs.find((r) => r.id === selected.id) || selected} onDecision={decide} /> : null}
        </div>
      </main>
      {toast ? (
        <div style={{ position: 'fixed', right: 24, bottom: 24, zIndex: 1200 }}>
          <DSa.Toast kind={toast.kind} title={toast.title} description={toast.description} onDismiss={() => setToast(null)} />
        </div>
      ) : null}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
