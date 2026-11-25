import React, { useState } from 'react';

/**
 * Frosted glass panel — the base surface of every DCT view.
 * Interactive cards lift 2px on hover; static cards never move.
 */
export function Card({ title, subtitle, action, interactive = false, onClick, padding = 'var(--space-5)', style, children }) {
  const [hover, setHover] = useState(false);
  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        background: 'var(--surface-glass)',
        backdropFilter: 'var(--blur-glass)', WebkitBackdropFilter: 'var(--blur-glass)',
        border: `1px solid ${interactive && hover ? 'var(--border-strong)' : 'var(--border-hairline)'}`,
        borderRadius: 'var(--radius-lg)',
        boxShadow: interactive && hover ? 'var(--shadow-raised)' : 'var(--shadow-card)',
        padding,
        transform: interactive && hover ? 'var(--lift-hover)' : 'none',
        cursor: interactive ? 'pointer' : 'default',
        transition: 'transform var(--duration-base) var(--ease-out), box-shadow var(--duration-base) var(--ease-out), border-color var(--duration-base) var(--ease-out)',
        fontFamily: 'var(--font-sans)',
        ...style,
      }}
    >
      {(title || action) ? (
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 'var(--space-4)', marginBottom: children ? 'var(--space-4)' : 0 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
            {title ? <div style={{ fontSize: 'var(--text-md)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-1)', letterSpacing: 'var(--tracking-tight)' }}>{title}</div> : null}
            {subtitle ? <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-2)' }}>{subtitle}</div> : null}
          </div>
          {action ? <div style={{ flexShrink: 0 }}>{action}</div> : null}
        </div>
      ) : null}
      {children}
    </div>
  );
}
