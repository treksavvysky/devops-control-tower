import Link from 'next/link';

async function getReviews() {
    try {
        const res = await fetch('http://127.0.0.1:8000/cwom/issues?status=under_review', { cache: 'no-store' });
        if (!res.ok) return [];
        return res.json();
    } catch (e) {
        console.error(e);
        return [];
    }
}

export default async function ReviewsPage() {
    const issues = await getReviews();

    return (
        <div className="animate-fade-in">
            <div className="header">
                <h1>Human in the Loop Queue</h1>
                <p>Review and approve agent tasks before they are executed or finalized.</p>
            </div>

            {issues.length === 0 ? (
                <div className="glass-panel" style={{ padding: '3rem', textAlign: 'center' }}>
                    <h3 className="text-muted" style={{ marginBottom: '1rem' }}>No pending reviews</h3>
                    <p className="text-muted">The queue is currently empty. All agents are operational and unblocked.</p>
                </div>
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    {issues.map((issue: any) => (
                        <Link href={`/reviews/${issue.id}`} key={issue.id} style={{ textDecoration: 'none' }}>
                            <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <div>
                                    <div className="flex-gap-2 mb-1" style={{ alignItems: 'center' }}>
                                        <span style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: '1.1rem' }}>{issue.title}</span>
                                        <span className="badge badge-yellow" style={{ background: 'rgba(245, 158, 11, 0.15)', color: '#fcd34d', border: '1px solid rgba(245, 158, 11, 0.3)' }}>
                                            Pending Review
                                        </span>
                                    </div>
                                    <div className="text-sm text-muted">
                                        ID: {issue.id} • Type: {issue.type || 'unknown'} • Repo: {issue.repo?.id || 'unknown'}
                                    </div>
                                </div>
                                <div>
                                    <span className="btn btn-primary">Review Task</span>
                                </div>
                            </div>
                        </Link>
                    ))}
                </div>
            )}
        </div>
    );
}
