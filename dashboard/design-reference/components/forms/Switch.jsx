import React from 'react';

/**
 * Toggle switch — blue gradient track when on, gentle slide.
 */
export function Switch({ checked = false, onChange, label, disabled = false, style }) {
  return (
    <label style={{ display: 'inline-flex', alignItems: 'center', gap: '10px', cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.45 : 1, fontFamily: 'var(--font-sans)', ...style }}>
      <input
        type="checkbox" role="switch" checked={checked} disabled={disabled}
        onChange={(e) => onChange && onChange(e.target.checked)}
        style={{ position: 'absolute', opacity: 0, width: 0, height: 0 }}
      />
      <span style={{
        display: 'inline-flex', alignItems: 'center', width: 36, height: 20, flexShrink: 0,
        padding: '2px', borderRadius: 'var(--radius-pill)',
        background: checked ? 'var(--grad-blue)' : 'rgba(255,255,255,0.1)',
        border: '1px solid var(--border-hairline)',
        boxShadow: checked ? 'var(--glow-blue)' : 'none',
        transition: 'background var(--duration-base) var(--ease-out), box-shadow var(--duration-base) var(--ease-out)',
      }}>
        <span style={{
          width: 14, height: 14, borderRadius: '50%', background: '#fff',
          boxShadow: '0 1px 2px rgba(0,0,0,0.4)',
          transform: checked ? 'translateX(16px)' : 'translateX(0)',
          transition: 'transform var(--duration-base) var(--ease-out)',
        }}></span>
      </span>
      {label ? <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-1)' }}>{label}</span> : null}
    </label>
  );
}
