'use client';

import { useState } from 'react';
import type { ReactNode } from 'react';
import {
  Badge,
  Button,
  Card,
  Checkbox,
  Dialog,
  EmptyState,
  IconButton,
  Input,
  PageHeader,
  Radio,
  Select,
  Stat,
  StatusBadge,
  Switch,
  Tabs,
  Tag,
  Textarea,
  Toast,
  Tooltip,
} from '@/components/ui';
import { Icon } from '@/components/icons/Icon';
import { ICON_NAMES } from '@/components/icons/icon-data';

const ACCENTS = [
  { name: 'blue', token: '--accent-blue', hex: '#3b82f6', usage: 'Action · running · links' },
  { name: 'green', token: '--accent-green', hex: '#10b981', usage: 'Approved · passed' },
  { name: 'amber', token: '--accent-amber', hex: '#f59e0b', usage: 'Pending review · needs changes' },
  { name: 'red', token: '--accent-red', hex: '#ef4444', usage: 'Rejected · failed' },
];

const SURFACES = [
  { token: '--bg-0', usage: 'App background' },
  { token: '--bg-inset', usage: 'Wells, code, logs' },
  { token: '--surface-glass', usage: 'Frosted panels' },
  { token: '--text-1', usage: 'Primary text' },
  { token: '--text-2', usage: 'Secondary text' },
  { token: '--text-3', usage: 'Muted / metadata' },
];

const SPACING = ['1', '2', '3', '4', '5', '6', '8', '10', '12'];

const CWOM_STATUSES = ['planned', 'ready', 'running', 'blocked', 'under_review', 'done', 'failed', 'canceled'];
const VERDICTS = ['pass', 'fail', 'partial', 'pending'];
const DECISIONS = ['approved', 'rejected', 'needs_changes'];

function Section({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <Card title={title} subtitle={subtitle}>
      {children}
    </Card>
  );
}

export function DesignShowcase() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [checked, setChecked] = useState(true);
  const [radio, setRadio] = useState('agent');
  const [switched, setSwitched] = useState(true);

  return (
    <div>
      <PageHeader
        title="Design system"
        subtitle="Living reference for the DCT Design System — synced from Claude Design. Tokens: src/styles/tokens · Components: src/components/ui."
      />

      <div className="stack-5">
        <Section title="Semantic accents" subtitle="The only saturated colors in the system. Never decorative.">
          <div className="grid-cols-2">
            {ACCENTS.map((a) => (
              <div key={a.name} className="flex-center flex-gap-4">
                <span
                  style={{
                    width: 44,
                    height: 44,
                    borderRadius: 'var(--radius-md)',
                    background: `var(${a.token})`,
                    flexShrink: 0,
                  }}
                />
                <div style={{ lineHeight: 1.4 }}>
                  <div>
                    <strong>{a.name}</strong> <code className="mono text-xs text-muted">{a.hex}</code>
                  </div>
                  <div className="text-sm text-secondary">{a.usage}</div>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-4 stack-2">
            {SURFACES.map((s) => (
              <div key={s.token} className="flex-center flex-gap-3">
                <span
                  style={{
                    width: 28,
                    height: 28,
                    borderRadius: 'var(--radius-sm)',
                    background: `var(${s.token})`,
                    border: '1px solid var(--border-strong)',
                    flexShrink: 0,
                  }}
                />
                <code className="mono text-sm">{s.token}</code>
                <span className="text-sm text-muted">{s.usage}</span>
              </div>
            ))}
          </div>
        </Section>

        <Section title="Typography" subtitle="Inter for UI; JetBrains Mono for run IDs, hashes, and logs.">
          <div className="stack-2">
            <div style={{ fontSize: 'var(--text-xl)', fontWeight: 700, letterSpacing: 'var(--tracking-tight)', background: 'var(--grad-headline)', WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent' }}>
              Page title — 28px bold, gradient fill
            </div>
            <div style={{ fontSize: 'var(--text-lg)', fontWeight: 700 }}>Section heading — 22px bold</div>
            <div style={{ fontSize: 'var(--text-md)', fontWeight: 600 }}>Card title — 17px semibold</div>
            <div style={{ fontSize: 'var(--text-base)' }}>Body — 15px regular, 1.6 leading</div>
            <div className="text-sm text-secondary">Metadata — 13px secondary</div>
            <div className="text-xs" style={{ textTransform: 'uppercase', letterSpacing: 'var(--tracking-label)', fontWeight: 600, color: 'var(--text-2)' }}>
              Tracked label — 11px uppercase
            </div>
            <code className="mono text-sm">run_8f3ka92 · sha:1f8c2ea · feat/billing-queue</code>
            <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, fontVariantNumeric: 'tabular-nums', color: 'var(--accent-green)' }}>
              98.2%
            </div>
          </div>
        </Section>

        <Section title="Spacing" subtitle="4px base scale.">
          <div className="stack-2">
            {SPACING.map((s) => (
              <div key={s} className="flex-center flex-gap-3">
                <code className="mono text-xs text-muted" style={{ width: 80 }}>--space-{s}</code>
                <span style={{ height: 10, width: `var(--space-${s})`, background: 'var(--accent-blue)', borderRadius: 2 }} />
              </div>
            ))}
          </div>
        </Section>

        <Section title="Icons" subtitle="Lucide, 2px stroke, colored by context via currentColor.">
          <div className="flex-gap-2 flex-wrap" style={{ display: 'flex' }}>
            {ICON_NAMES.map((name) => (
              <Tooltip key={name} content={name}>
                <span
                  className="flex-center"
                  style={{
                    width: 36,
                    height: 36,
                    justifyContent: 'center',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--border-hairline)',
                    background: 'var(--surface-glass-2)',
                    color: 'var(--text-2)',
                  }}
                >
                  <Icon name={name} size={16} />
                </span>
              </Tooltip>
            ))}
          </div>
        </Section>

        <Section title="Buttons" subtitle="Gradient fills for the three semantic actions; glass secondary; quiet ghost.">
          <div className="stack-4">
            <div className="flex-gap-2 flex-wrap" style={{ display: 'flex' }}>
              <Button icon="play">Primary</Button>
              <Button variant="success" icon="check">Approve &amp; merge</Button>
              <Button variant="danger" icon="x">Reject run</Button>
              <Button variant="secondary" icon="eye">Secondary</Button>
              <Button variant="ghost" icon="clock">Ghost</Button>
              <Button disabled>Disabled</Button>
            </div>
            <div className="flex-center flex-gap-2">
              <Button size="sm">Small</Button>
              <Button size="md">Medium</Button>
              <Button size="lg">Large</Button>
            </div>
            <div className="flex-center flex-gap-2">
              <IconButton icon="copy" label="Copy" />
              <IconButton icon="external-link" label="Open" />
              <IconButton icon="ellipsis" label="More" variant="ghost" />
              <IconButton icon="x" label="Delete" variant="danger" />
              <IconButton icon="settings" label="Settings" size="lg" />
            </div>
          </div>
        </Section>

        <Section title="Badges & status vocabulary" subtitle="Status is strictly semantic. Domain statuses render through StatusBadge — never hand-pick a color.">
          <div className="stack-4">
            <div className="flex-gap-2 flex-wrap" style={{ display: 'flex' }}>
              <Badge status="running" dot pulse>Running</Badge>
              <Badge status="approved">Approved</Badge>
              <Badge status="pending">Needs review</Badge>
              <Badge status="rejected">Rejected</Badge>
              <Badge status="neutral">Neutral</Badge>
            </div>
            <div>
              <div className="text-xs text-muted mb-2" style={{ textTransform: 'uppercase', letterSpacing: 'var(--tracking-label)', fontWeight: 600 }}>CWOM statuses</div>
              <div className="flex-gap-2 flex-wrap" style={{ display: 'flex' }}>
                {CWOM_STATUSES.map((s) => <StatusBadge key={s} status={s} dot={s === 'running'} />)}
              </div>
            </div>
            <div>
              <div className="text-xs text-muted mb-2" style={{ textTransform: 'uppercase', letterSpacing: 'var(--tracking-label)', fontWeight: 600 }}>Evidence verdicts</div>
              <div className="flex-gap-2 flex-wrap" style={{ display: 'flex' }}>
                {VERDICTS.map((s) => <StatusBadge key={s} status={s} />)}
              </div>
            </div>
            <div>
              <div className="text-xs text-muted mb-2" style={{ textTransform: 'uppercase', letterSpacing: 'var(--tracking-label)', fontWeight: 600 }}>Review decisions</div>
              <div className="flex-gap-2 flex-wrap" style={{ display: 'flex' }}>
                {DECISIONS.map((s) => <StatusBadge key={s} status={s} />)}
              </div>
            </div>
            <div className="flex-gap-2 flex-wrap" style={{ display: 'flex' }}>
              <Tag icon="git-branch" mono>feat/billing-queue</Tag>
              <Tag icon="box" mono>core-api</Tag>
              <Tag icon="shield" mono>strict-prod</Tag>
              <Tag icon="list-checks">12 checks</Tag>
              <Tag onRemove={() => undefined}>removable</Tag>
            </div>
          </div>
        </Section>

        <Section title="Cards & stats">
          <div className="grid-cols-2">
            <Card title="Static card" subtitle="Never moves on hover" action={<Badge status="neutral">v0</Badge>}>
              <p className="text-sm text-secondary" style={{ margin: 0 }}>
                The base glass surface of every DCT view.
              </p>
            </Card>
            <Card title="Interactive card" subtitle="Lifts 2px — it navigates somewhere" interactive>
              <p className="text-sm text-secondary" style={{ margin: 0 }}>
                Hover to see the lift and raised shadow.
              </p>
            </Card>
          </div>
          <div className="grid-cols-3 mt-4">
            <Stat label="Active agents" value={12} accent="blue" detail="3 of 4 running" />
            <Stat label="Pass rate" value="98.2%" accent="green" detail="Last 7 days" />
            <Stat label="Awaiting review" value={4} accent="amber" detail="Oldest: 2h" />
          </div>
        </Section>

        <Section title="Forms" subtitle="Inset dark wells with a blue focus ring.">
          <div className="grid-cols-2">
            <div className="stack-4">
              <Input label="Search" icon="search" placeholder="Search runs, agents, tasks" />
              <Input label="Run ID" mono defaultValue="run_8f3ka92" />
              <Input label="Repo" error="Repo is not on the allowlist" defaultValue="unknown/repo" />
              <Textarea label="Decision reasoning" placeholder="Explain the approval or rejection reasoning…" />
            </div>
            <div className="stack-4">
              <Select label="Repository" options={['all repos', 'core-api', 'edge-proxy']} />
              <Checkbox checked={checked} onChange={setChecked} label="Require passing checks" />
              <div className="stack-2">
                <Radio name="mode" value="agent" checked={radio === 'agent'} onChange={setRadio} label="Agent execution" />
                <Radio name="mode" value="human" checked={radio === 'human'} onChange={setRadio} label="Human execution" />
              </div>
              <Switch checked={switched} onChange={setSwitched} label="Auto-approve passing runs" />
            </div>
          </div>
        </Section>

        <Section title="Navigation & overlays">
          <div className="stack-4">
            <Tabs
              tabs={[
                { value: 'checks', label: 'Checks', count: 12 },
                { value: 'artifacts', label: 'Artifacts', count: 3 },
                { value: 'log', label: 'Log' },
              ]}
              defaultValue="checks"
            />
            <div className="flex-center flex-gap-2">
              <Tooltip content="Copy run ID">
                <IconButton icon="copy" label="Copy run ID" size="sm" />
              </Tooltip>
              <Tooltip content="Tooltips appear on hover and focus" side="bottom">
                <Button variant="secondary" size="sm">Hover me</Button>
              </Tooltip>
              <Button variant="secondary" size="sm" icon="external-link" onClick={() => setDialogOpen(true)}>
                Open dialog
              </Button>
            </div>
            <div className="grid-cols-2">
              <Toast kind="success" title="Approved" description="Merged to main." style={{ width: '100%' }} />
              <Toast kind="error" title="Rejected" description="Returned to queue with notes." style={{ width: '100%' }} />
              <Toast kind="warning" title="Awaiting review" description="4 runs need a decision." style={{ width: '100%' }} />
              <Toast kind="info" title="Agent restarted" description="builder-2 resumed task." style={{ width: '100%' }} />
            </div>
          </div>
        </Section>

        <Section title="Empty state">
          <EmptyState
            icon="circle-check"
            title="No pending reviews"
            description="The queue is empty. All agents are operational and unblocked."
            action={<Button variant="secondary" size="sm" icon="arrow-right">Back to overview</Button>}
          />
        </Section>
      </div>

      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        title="Approve this run?"
        subtitle="run_8f3ka92 · core-api"
        footer={
          <>
            <Button variant="ghost" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button variant="success" icon="check" onClick={() => setDialogOpen(false)}>Approve &amp; merge</Button>
          </>
        }
      >
        All 12 checks passed under strict-prod. Approving merges the branch to main and closes the task.
      </Dialog>
    </div>
  );
}
