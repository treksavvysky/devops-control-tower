import React from 'react';
import { Icon } from '../icons/Icon.jsx';
import { IconButton } from '../actions/IconButton.jsx';

const KINDS = {
  info: { icon: 'info', color: 'var(--accent-blue)', tint: 'var(--tint-blue)', line: 'var(--line-blue)' },
  success: { icon: 'circle-check', color: 'var(--accent-green)', tint: 'var(--tint-green)', line: 'var(--line-green)' },
  warning: { icon: 'triangle-alert', color: 'var(--accent-amber)', tint: 'var(--tint-amber)', line: 'var(--line-amber)' },
  error: { icon: 'circle-x', color: 'var(--accent-red)', tint: 'var(--tint-red)', line: 'var(--line-red)' },
};

/**
 * Toast / inline callout — glass panel with a semantic tint stripe.
 * Render inside a fixed container for toasts, or inline as a callout.
 */
export function Toast({ kind = 'info', title, description, onDismiss, style }) {
  const k = KINDS[kind] || KINDS.info;
  return (
    <div style={{
      display: 'flex', alignItems: 'flex-start', gap: '10px',
      width: 360, maxWidth: '100%', padding: '12px 14px',
      background: 'var(--surface-glass)',
      backdropFilter: 'var(--blur-glass)', WebkitBackdropFilter: 'var(--blur-glass)',
      border: `1px solid ${k.line}`,
      borderRadius: 'var(--radius-md)',
      boxShadow: 'var(--shadow-raised)',
      fontFamily: 'var(--font-sans)',
      animation: 'dct-fade-in var(--duration-base) var(--ease-out)',
      ...style,
    }}>
      <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: 26, height: 26, flexShrink: 0, borderRadius: '8px', background: k.tint, color: k.color }}>
        <Icon name={k.icon} size={15} />
      </span>
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: '1px' }}>
        {title ? <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-1)' }}>{title}</div> : null}
        {description ? <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-2)' }}>{description}</div> : null}
      </div>
      {onDismiss ? <IconButton icon="x" label="Dismiss" variant="ghost" size="sm" onClick={onDismiss} /> : null}
    </div>
  );
}
