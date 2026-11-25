import React from 'react';

/**
 * Custom radio — blue ring with inner dot when selected.
 */
export function Radio({ checked = false, onChange, label, name, value, disabled = false, style }) {
  return (
    <label style={{ display: 'inline-flex', alignItems: 'center', gap: '9px', cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.45 : 1, fontFamily: 'var(--font-sans)', ...style }}>
      <input
        type="radio" checked={checked} name={name} value={value} disabled={disabled}
        onChange={() => onChange && onChange(value)}
        style={{ position: 'absolute', opacity: 0, width: 0, height: 0 }}
      />
      <span style={{
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        width: 18, height: 18, flexShrink: 0, borderRadius: '50%',
        background: 'var(--bg-inset)',
        border: `1px solid ${checked ? 'var(--accent-blue)' : 'var(--border-strong)'}`,
        transition: 'border-color var(--duration-fast) var(--ease-out)',
      }}>
        <span style={{
          width: 8, height: 8, borderRadius: '50%',
          background: 'var(--accent-blue)',
          transform: checked ? 'scale(1)' : 'scale(0)',
          transition: 'transform var(--duration-fast) var(--ease-out)',
        }}></span>
      </span>
      {label ? <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-1)' }}>{label}</span> : null}
    </label>
  );
}
