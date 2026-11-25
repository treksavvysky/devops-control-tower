import Link from 'next/link';
import { Badge, Card, EmptyState, PageHeader, Tag } from '@/components/ui';
import { Icon } from '@/components/icons/Icon';
import { API_BASE } from '@/lib/api';
import type { Issue } from '@/lib/types';

async function getReviews(): Promise<Issue[]> {
    try {
        const res = await fetch(`${API_BASE}/cwom/issues?status=under_review`, { cache: 'no-store' });
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
        <div>
            <PageHeader
                title="Review queue"
                subtitle="Human gate — review agent work before it is finalized."
            />

            {issues.length === 0 ? (
                <EmptyState
                    icon="circle-check"
                    title="No pending reviews"
                    description="The queue is empty. All agents are operational and unblocked."
                />
            ) : (
                <div className="stack-4">
                    <div className="flex-center flex-gap-2">
                        <span className="text-sm text-muted">{issues.length} awaiting review</span>
                    </div>
                    {issues.map((issue) => (
                        <Link href={`/reviews/${issue.id}`} key={issue.id} style={{ textDecoration: 'none' }}>
                            <Card interactive>
                                <div className="flex-center flex-gap-4">
                                    <span
                                        style={{
                                            display: 'inline-flex',
                                            alignItems: 'center',
                                            justifyContent: 'center',
                                            width: 38,
                                            height: 38,
                                            borderRadius: 11,
                                            flexShrink: 0,
                                            background: 'var(--tint-amber)',
                                            border: '1px solid var(--line-amber)',
                                            color: 'var(--accent-amber)',
                                        }}
                                    >
                                        <Icon name="eye" size={17} />
                                    </span>
                                    <div style={{ flex: 1, minWidth: 0, lineHeight: 1.4 }}>
                                        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
                                            <span
                                                style={{
                                                    fontSize: 'var(--text-md)',
                                                    fontWeight: 600,
                                                    color: 'var(--text-1)',
                                                }}
                                            >
                                                {issue.title}
                                            </span>
                                            <code className="mono text-xs text-muted">{issue.id}</code>
                                        </div>
                                        <div className="flex-gap-2 mt-2">
                                            <Tag icon="box" mono>{issue.repo?.id || 'unknown'}</Tag>
                                            <Tag icon="git-branch">{issue.type || 'unknown'}</Tag>
                                        </div>
                                    </div>
                                    <Badge status="pending">Needs review</Badge>
                                </div>
                            </Card>
                        </Link>
                    ))}
                </div>
            )}
        </div>
    );
}
