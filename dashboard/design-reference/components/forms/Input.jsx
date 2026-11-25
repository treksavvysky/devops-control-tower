import React, { useState } from 'react';
import { Icon } from '../icons/Icon.jsx';

/**
 * Text input on an inset dark well with a hairline border; blue focus ring.
 */
export function Input({ label, icon, error, mono = false, style, inputStyle, ...rest }) {
  const [focus, setFocus] = useState(false);
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontFamily: 'var(--font-sans)', ...style }}>
      {label ? (
        <span style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-semibold)', textTransform: 'uppercase', letterSpacing: 'var(--tracking-label)', color: 'var(--text-2)' }}>
          {label}
        </span>
      ) : null}
      <span style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
        {icon ? (
          <span style={{ position: 'absolute', left: 12, display: 'flex', color: 'var(--text-3)', pointerEvents: 'none' }}>
            <Icon name={icon} size={15} />
          </span>
        ) : null}
        <input
          onFocus={() => setFocus(true)}
          onBlur={() => setFocus(false)}
          style={{
            width: '100%', padding: icon ? '9px 12px 9px 36px' : '9px 12px',
            background: 'var(--bg-inset)', color: 'var(--text-1)',
            border: `1px solid ${error ? 'var(--line-red)' : focus ? 'var(--accent-blue)' : 'var(--border-hairline)'}`,
            borderRadius: 'var(--radius-sm)',
            fontFamily: mono ? 'var(--font-mono)' : 'var(--font-sans)', fontSize: 'var(--text-sm)',
            outline: 'none',
            boxShadow: focus ? '0 0 0 3px rgba(59,130,246,0.18)' : 'none',
            transition: 'border-color var(--duration-fast) var(--ease-out), box-shadow var(--duration-fast) var(--ease-out)',
            ...inputStyle,
          }}
          {...rest}
        />
      </span>
      {error ? (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', fontSize: 'var(--text-xs)', color: 'var(--accent-red)' }}>
          <Icon name="triangle-alert" size={12} /> {error}
        </span>
      ) : null}
    </label>
  );
}
