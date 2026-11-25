import React from 'react';

const ACCENTS = {
  blue: 'var(--accent-blue)',
  green: 'var(--accent-green)',
  amber: 'var(--accent-amber)',
  red: 'var(--accent-red)',
  neutral: 'var(--text-1)',
};

/**
 * Big confident stat — 2.5rem bold number in an accent color over a small
 * uppercase label. The accent must match the number's meaning.
 */
export function Stat({ label, value, accent = 'neutral', detail, style }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontFamily: 'var(--font-sans)', ...style }}>
      <span style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-semibold)', textTransform: 'uppercase', letterSpacing: 'var(--tracking-label)', color: 'var(--text-2)' }}>
        {label}
      </span>
      <span style={{ fontSize: 'var(--text-2xl)', fontWeight: 'var(--weight-bold)', lineHeight: 1.1, letterSpacing: 'var(--tracking-tight)', color: ACCENTS[accent] || ACCENTS.neutral, fontVariantNumeric: 'tabular-nums' }}>
        {value}
      </span>
      {detail ? <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-3)' }}>{detail}</span> : null}
    </div>
  );
}
