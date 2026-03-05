import Link from "next/link";

export default function Home() {
  return (
    <div className="animate-fade-in">
      <div className="header">
        <h1>Command Center</h1>
        <p>Monitor system health and pending agent tasks.</p>
      </div>

      <div className="grid-cols-3">
        <div className="glass-panel" style={{ padding: '2rem' }}>
          <h3 className="text-muted mb-2">Active Agents</h3>
          <div style={{ fontSize: '2.5rem', fontWeight: 700, color: 'var(--accent-blue)' }}>12</div>
          <div className="text-sm text-muted mt-4">Running in isolated contexts</div>
        </div>

        <div className="glass-panel" style={{ padding: '2rem' }}>
          <h3 className="text-muted mb-2">Pending Reviews</h3>
          <div style={{ fontSize: '2.5rem', fontWeight: 700, color: 'var(--accent-yellow)' }}>Wait</div>
          <div className="text-sm mt-4">
            <Link href="/reviews" className="btn btn-primary" style={{ textDecoration: 'none' }}>Go to Queue</Link>
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '2rem' }}>
          <h3 className="text-muted mb-2">Tasks Completed</h3>
          <div style={{ fontSize: '2.5rem', fontWeight: 700, color: 'var(--accent-green)' }}>1,432</div>
          <div className="text-sm text-muted mt-4">In the last 7 days</div>
        </div>
      </div>

      <div className="mt-4 glass-panel" style={{ padding: '2rem' }}>
        <h3 className="mb-4">Recent Activity</h3>
        <p className="text-muted">Orchestrator log streaming goes here...</p>
      </div>
    </div>
  );
}
