import React from 'react';

const STATUS = {
  running: { color: 'var(--accent-blue)', tint: 'var(--tint-blue)', line: 'var(--line-blue)' },
  approved: { color: 'var(--accent-green)', tint: 'var(--tint-green)', line: 'var(--line-green)' },
  pending: { color: 'var(--accent-amber)', tint: 'var(--tint-amber)', line: 'var(--line-amber)' },
  rejected: { color: 'var(--accent-red)', tint: 'var(--tint-red)', line: 'var(--line-red)' },
  neutral: { color: 'var(--text-2)', tint: 'rgba(255,255,255,0.06)', line: 'var(--border-strong)' },
};

/**
 * Pill-shaped uppercase status badge. Status is strictly semantic:
 * running=blue, approved=green, pending=amber, rejected=red.
 */
export function Badge({ status = 'neutral', dot = false, pulse = false, style, children }) {
  const s = STATUS[status] || STATUS.neutral;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '6px',
      padding: '3px 10px',
      background: s.tint, color: s.color,
      border: `1px solid ${s.line}`,
      borderRadius: 'var(--radius-pill)',
      fontFamily: 'var(--font-sans)', fontSize: 'var(--text-xs)',
      fontWeight: 'var(--weight-semibold)', textTransform: 'uppercase',
      letterSpacing: 'var(--tracking-label)', whiteSpace: 'nowrap',
      ...style,
    }}>
      {dot ? (
        <span style={{
          width: 6, height: 6, borderRadius: '50%', background: s.color,
          animation: pulse ? 'dct-pulse 1.6s ease-in-out infinite' : 'none',
        }}></span>
      ) : null}
      {children}
    </span>
  );
}
