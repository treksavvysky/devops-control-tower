'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { use } from 'react';

export default function ReviewDetailPage({ params }: { params: Promise<{ id: string }> }) {
    const router = useRouter();
    const unwrappedParams = use(params);
    const issueId = unwrappedParams.id;

    const [issue, setIssue] = useState<any>(null);
    const [evidencePacks, setEvidencePacks] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [reason, setReason] = useState('Reviewed manually. Looks good to me.');
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        async function fetchData() {
            try {
                const [issueRes, packsRes] = await Promise.all([
                    fetch(`http://127.0.0.1:8000/cwom/issues/${issueId}`),
                    fetch(`http://127.0.0.1:8000/cwom/issues/${issueId}/evidence-packs`)
                ]);

                if (issueRes.ok) setIssue(await issueRes.json());
                if (packsRes.ok) setEvidencePacks(await packsRes.json());
            } catch (err: any) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        }
        fetchData();
    }, [issueId]);

    const submitReview = async (decision: 'approved' | 'rejected' | 'needs_changes') => {
        if (!evidencePacks.length) {
            alert("No evidence pack found for this issue.");
            return;
        }
        const pack = evidencePacks[0]; // using latest/first pack

        // Attempt to extract run ID directly from pack or defaults
        const runId = pack.for_run_id || (pack.for_run && pack.for_run.id) || "unknown_run";
        const packId = pack.id;

        setSubmitting(true);
        try {
            const payload = {
                for_evidence_pack: { kind: "EvidencePack", id: packId },
                for_run: { kind: "Run", id: runId },
                for_issue: { kind: "Issue", id: issueId },
                reviewer: { actor_kind: "human", actor_id: "human-operator", display: "Human Operator" },
                decision,
                decision_reason: reason
            };

            const res = await fetch('http://127.0.0.1:8000/cwom/reviews', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.detail || 'Failed to submit review');
            }

            router.push('/reviews');
            router.refresh();
        } catch (err: any) {
            alert("Error submitting review: " + err.message);
            setSubmitting(false);
        }
    };

    if (loading) return <div style={{ padding: '2rem' }}>Loading review details...</div>;
    if (!issue) return <div style={{ padding: '2rem' }}>Issue not found.</div>;

    const pack = evidencePacks[0] || {};
    const checksPassed = pack.checks_passed || 0;
    const checksFailed = pack.checks_failed || 0;

    return (
        <div className="animate-fade-in">
            <Link href="/reviews" style={{ color: 'var(--accent-blue)', textDecoration: 'none', marginBottom: '1.5rem', display: 'inline-block' }}>
                &larr; Back to Queue
            </Link>

            <div className="header">
                <h1>Decision Required</h1>
                <p>Review the operation results before finalizing.</p>
            </div>

            <div className="grid-cols-2">
                {/* Left Column - Details */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                    <div className="card">
                        <h3 className="mb-2">Objective</h3>
                        <p style={{ fontSize: '1.1rem', color: 'var(--text-primary)' }}>{issue.title}</p>
                        {issue.description && <p className="text-muted mt-4">{issue.description}</p>}

                        <div className="mt-4" style={{ display: 'flex', gap: '1rem' }}>
                            <div>
                                <span className="text-muted text-sm">Repo: </span>
                                <span className="badge badge-default">{issue.repo?.id || 'unknown'}</span>
                            </div>
                            <div>
                                <span className="text-muted text-sm">Type: </span>
                                <span className="badge badge-default">{issue.type || 'feature'}</span>
                            </div>
                        </div>
                    </div>

                    <div className="card">
                        <h3 className="mb-4">Evidence & Artifacts</h3>
                        {!evidencePacks.length ? (
                            <p className="text-muted">No evidence pack found.</p>
                        ) : (
                            <div>
                                <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem' }}>
                                    <div style={{ background: 'rgba(16, 185, 129, 0.1)', padding: '1rem', borderRadius: 8, flex: 1, border: '1px solid rgba(16, 185, 129, 0.2)' }}>
                                        <div style={{ fontSize: '1.5rem', color: '#10b981', fontWeight: 600 }}>{checksPassed}</div>
                                        <div className="text-sm">Checks Passed</div>
                                    </div>
                                    <div style={{ background: 'rgba(239, 68, 68, 0.1)', padding: '1rem', borderRadius: 8, flex: 1, border: '1px solid rgba(239, 68, 68, 0.2)' }}>
                                        <div style={{ fontSize: '1.5rem', color: '#ef4444', fontWeight: 600 }}>{checksFailed}</div>
                                        <div className="text-sm">Checks Failed</div>
                                    </div>
                                </div>
                                <div className="text-sm text-muted">
                                    <strong>Verdict:</strong> {pack.verdict || 'unknown'} <br />
                                    <strong>Reason:</strong> {pack.verdict_reason || 'none'}
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* Right Column - Actions */}
                <div>
                    <div className="card" style={{ position: 'sticky', top: '2rem' }}>
                        <h3 className="mb-4">Record Decision</h3>

                        <div className="mb-4">
                            <label className="text-sm text-muted mb-2" style={{ display: 'block' }}>Decision Reasoning</label>
                            <textarea
                                className="textarea"
                                value={reason}
                                onChange={e => setReason(e.target.value)}
                                placeholder="Explain the approval or rejection reasoning..."
                            />
                        </div>

                        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                            <button
                                className="btn btn-approve"
                                style={{ width: '100%', padding: '1rem', fontSize: '1rem' }}
                                onClick={() => submitReview('approved')}
                                disabled={submitting || !evidencePacks.length}
                            >
                                Approve & Execute
                            </button>

                            <div className="flex-gap-4">
                                <button
                                    className="btn btn-changes"
                                    style={{ flex: 1 }}
                                    onClick={() => submitReview('needs_changes')}
                                    disabled={submitting || !evidencePacks.length}
                                >
                                    Request Changes
                                </button>
                                <button
                                    className="btn btn-reject"
                                    style={{ flex: 1 }}
                                    onClick={() => submitReview('rejected')}
                                    disabled={submitting || !evidencePacks.length}
                                >
                                    Reject Run
                                </button>
                            </div>
                        </div>

                        {!evidencePacks.length && (
                            <p className="text-sm text-muted mt-4" style={{ color: '#f87171' }}>
                                Cannot record decision without an Evidence Pack.
                            </p>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
