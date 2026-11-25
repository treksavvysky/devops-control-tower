import React from 'react';
import { IconButton } from '../actions/IconButton.jsx';

/**
 * Modal dialog on a heavy-blur scrim. Calm entrance (fade only).
 */
export function Dialog({ open = false, onClose, title, subtitle, footer, width = 480, children }) {
  if (!open) return null;
  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'rgba(10, 12, 16, 0.6)',
        backdropFilter: 'blur(8px)', WebkitBackdropFilter: 'blur(8px)',
        animation: 'dct-fade-in var(--duration-base) var(--ease-out)',
        fontFamily: 'var(--font-sans)',
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
        style={{
          width, maxWidth: 'calc(100vw - 48px)', maxHeight: 'calc(100vh - 96px)',
          display: 'flex', flexDirection: 'column',
          background: 'var(--surface-glass)',
          backdropFilter: 'var(--blur-glass-heavy)', WebkitBackdropFilter: 'var(--blur-glass-heavy)',
          border: '1px solid var(--border-strong)',
          borderRadius: 'var(--radius-lg)',
          boxShadow: 'var(--shadow-overlay)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 'var(--space-4)', padding: 'var(--space-5) var(--space-5) 0' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
            {title ? <div style={{ fontSize: 'var(--text-lg)', fontWeight: 'var(--weight-bold)', letterSpacing: 'var(--tracking-tight)', color: 'var(--text-1)' }}>{title}</div> : null}
            {subtitle ? <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-2)' }}>{subtitle}</div> : null}
          </div>
          <IconButton icon="x" label="Close" variant="ghost" size="sm" onClick={onClose} />
        </div>
        <div style={{ padding: 'var(--space-4) var(--space-5)', overflowY: 'auto', fontSize: 'var(--text-base)', color: 'var(--text-1)' }}>
          {children}
        </div>
        {footer ? (
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-2)', padding: 'var(--space-4) var(--space-5)', borderTop: '1px solid var(--border-hairline)' }}>
            {footer}
          </div>
        ) : null}
      </div>
    </div>
  );
}
