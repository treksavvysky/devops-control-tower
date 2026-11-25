'use client';

import { useEffect, useState, use } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Icon } from '@/components/icons/Icon';
import {
    Badge,
    Button,
    Card,
    Stat,
    StatusBadge,
    Tag,
    Textarea,
    Toast,
} from '@/components/ui';
import { API_BASE } from '@/lib/api';
import type { EvidencePack, Issue } from '@/lib/types';

export default function ReviewDetailPage({ params }: { params: Promise<{ id: string }> }) {
    const router = useRouter();
    const unwrappedParams = use(params);
    const issueId = unwrappedParams.id;

    const [issue, setIssue] = useState<Issue | null>(null);
    const [evidencePacks, setEvidencePacks] = useState<EvidencePack[]>([]);
    const [loading, setLoading] = useState(true);
    const [reason, setReason] = useState('Reviewed manually. Looks good to me.');
    const [submitting, setSubmitting] = useState(false);
    const [submitError, setSubmitError] = useState<string | null>(null);

    useEffect(() => {
        async function fetchData() {
            try {
                const [issueRes, packsRes] = await Promise.all([
                    fetch(`${API_BASE}/cwom/issues/${issueId}`),
                    fetch(`${API_BASE}/cwom/issues/${issueId}/evidence-packs`)
                ]);

                if (issueRes.ok) setIssue(await issueRes.json());
                if (packsRes.ok) setEvidencePacks(await packsRes.json());
            } catch (err) {
                console.error(err);
            } finally {
                setLoading(false);
            }
        }
        fetchData();
    }, [issueId]);

    const submitReview = async (decision: 'approved' | 'rejected' | 'needs_changes') => {
        if (!evidencePacks.length) return;
        const pack = evidencePacks[0]; // using latest/first pack

        const runId = pack.for_run_id || (pack.for_run && pack.for_run.id) || "unknown_run";

        setSubmitting(true);
        setSubmitError(null);
        try {
            const payload = {
                for_evidence_pack: { kind: "EvidencePack", id: pack.id },
                for_run: { kind: "Run", id: runId },
                for_issue: { kind: "Issue", id: issueId },
                reviewer: { actor_kind: "human", actor_id: "human-operator", display: "Human Operator" },
                decision,
                decision_reason: reason
            };

            const res = await fetch(`${API_BASE}/cwom/reviews`, {
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
        } catch (err) {
            setSubmitError(err instanceof Error ? err.message : String(err));
            setSubmitting(false);
        }
    };

    if (loading) return <p className="text-sm text-secondary">Loading review details…</p>;
    if (!issue) return <p className="text-sm text-secondary">Issue not found.</p>;

    const pack: EvidencePack = evidencePacks[0] || { id: '' };
    const checksPassed = pack.checks_passed || 0;
    const checksFailed = pack.checks_failed || 0;

    return (
        <div>
            <div className="mb-4">
                <Link href="/reviews" className="back-link">
                    <Icon name="chevron-right" size={14} style={{ transform: 'rotate(180deg)' }} />
                    Back to queue
                </Link>
            </div>

            <div className="stack-5">
                <Card
                    title={issue.title}
                    subtitle={issue.description || 'Review the operation results before finalizing.'}
                    action={<Badge status="pending">Needs review</Badge>}
                >
                    <div className="flex-center flex-gap-2 flex-wrap">
                        <Tag icon="box" mono>{issue.repo?.id || 'unknown'}</Tag>
                        <Tag icon="git-branch">{issue.type || 'feature'}</Tag>
                        <Tag icon="file-check" mono>{issue.id}</Tag>
                    </div>
                </Card>

                <div
                    style={{
                        display: 'grid',
                        gridTemplateColumns: 'minmax(0, 1fr) 340px',
                        gap: 'var(--space-5)',
                        alignItems: 'start',
                    }}
                >
                    <Card title="Evidence summary" subtitle="Automated checks from the prove step">
                        {!evidencePacks.length ? (
                            <p className="text-sm text-muted" style={{ margin: 0 }}>No evidence pack found.</p>
                        ) : (
                            <div className="stack-4">
                                <div className="grid-cols-2">
                                    <Stat
                                        label="Checks passed"
                                        value={checksPassed}
                                        accent="green"
                                    />
                                    <Stat
                                        label="Checks failed"
                                        value={checksFailed}
                                        accent={checksFailed > 0 ? 'red' : 'neutral'}
                                    />
                                </div>
                                <div className="flex-center flex-gap-2">
                                    <span className="text-xs text-muted" style={{ textTransform: 'uppercase', letterSpacing: 'var(--tracking-label)', fontWeight: 600 }}>
                                        Verdict
                                    </span>
                                    <StatusBadge status={pack.verdict} />
                                </div>
                                <p className="text-sm text-secondary" style={{ margin: 0 }}>
                                    {pack.verdict_reason || 'No verdict reason recorded.'}
                                </p>
                            </div>
                        )}
                    </Card>

                    <Card title="Review decision" subtitle="Human gate — final call" style={{ position: 'sticky', top: 0 }}>
                        <div className="stack-4">
                            <Textarea
                                label="Decision reasoning"
                                value={reason}
                                onChange={e => setReason(e.target.value)}
                                placeholder="Explain the approval or rejection reasoning…"
                            />

                            <div className="stack-2" style={{ gap: 10 }}>
                                <Button
                                    variant="success"
                                    icon="check"
                                    onClick={() => submitReview('approved')}
                                    disabled={submitting || !evidencePacks.length}
                                >
                                    Approve &amp; finalize
                                </Button>
                                <Button
                                    variant="danger"
                                    icon="x"
                                    onClick={() => submitReview('rejected')}
                                    disabled={submitting || !evidencePacks.length}
                                >
                                    Reject run
                                </Button>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    icon="clock"
                                    onClick={() => submitReview('needs_changes')}
                                    disabled={submitting || !evidencePacks.length}
                                >
                                    Request changes
                                </Button>
                            </div>

                            {!evidencePacks.length ? (
                                <Toast
                                    kind="warning"
                                    title="No evidence pack"
                                    description="A decision can't be recorded without an evidence pack."
                                    style={{ width: '100%' }}
                                />
                            ) : null}
                            {submitError ? (
                                <Toast
                                    kind="error"
                                    title="Submission failed"
                                    description={submitError}
                                    style={{ width: '100%' }}
                                />
                            ) : null}
                        </div>
                    </Card>
                </div>
            </div>
        </div>
    );
}
