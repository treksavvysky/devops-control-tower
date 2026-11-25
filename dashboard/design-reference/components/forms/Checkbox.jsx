import React from 'react';
import { Icon } from '../icons/Icon.jsx';

/**
 * Custom checkbox — blue fill with white check when on.
 */
export function Checkbox({ checked = false, onChange, label, disabled = false, style }) {
  return (
    <label style={{ display: 'inline-flex', alignItems: 'center', gap: '9px', cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.45 : 1, fontFamily: 'var(--font-sans)', ...style }}>
      <input
        type="checkbox" checked={checked} disabled={disabled}
        onChange={(e) => onChange && onChange(e.target.checked)}
        style={{ position: 'absolute', opacity: 0, width: 0, height: 0 }}
      />
      <span style={{
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        width: 18, height: 18, flexShrink: 0,
        background: checked ? 'var(--grad-blue)' : 'var(--bg-inset)',
        border: `1px solid ${checked ? 'var(--accent-blue)' : 'var(--border-strong)'}`,
        borderRadius: '5px', color: '#fff',
        transition: 'background var(--duration-fast) var(--ease-out), border-color var(--duration-fast) var(--ease-out)',
      }}>
        {checked ? <Icon name="check" size={12} strokeWidth={3} /> : null}
      </span>
      {label ? <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-1)' }}>{label}</span> : null}
    </label>
  );
}
