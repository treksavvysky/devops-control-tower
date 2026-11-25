import React, { useState } from 'react';
import { Icon } from '../icons/Icon.jsx';

/**
 * Native select styled as an inset dark well with a chevron affordance.
 */
export function Select({ label, options = [], style, selectStyle, ...rest }) {
  const [focus, setFocus] = useState(false);
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontFamily: 'var(--font-sans)', ...style }}>
      {label ? (
        <span style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-semibold)', textTransform: 'uppercase', letterSpacing: 'var(--tracking-label)', color: 'var(--text-2)' }}>
          {label}
        </span>
      ) : null}
      <span style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
        <select
          onFocus={() => setFocus(true)}
          onBlur={() => setFocus(false)}
          style={{
            width: '100%', padding: '9px 32px 9px 12px', appearance: 'none', WebkitAppearance: 'none',
            background: 'var(--bg-inset)', color: 'var(--text-1)',
            border: `1px solid ${focus ? 'var(--accent-blue)' : 'var(--border-hairline)'}`,
            borderRadius: 'var(--radius-sm)',
            fontFamily: 'var(--font-sans)', fontSize: 'var(--text-sm)',
            outline: 'none', cursor: 'pointer',
            boxShadow: focus ? '0 0 0 3px rgba(59,130,246,0.18)' : 'none',
            transition: 'border-color var(--duration-fast) var(--ease-out), box-shadow var(--duration-fast) var(--ease-out)',
            ...selectStyle,
          }}
          {...rest}
        >
          {options.map((o) => {
            const opt = typeof o === 'string' ? { value: o, label: o } : o;
            return <option key={opt.value} value={opt.value}>{opt.label}</option>;
          })}
        </select>
        <span style={{ position: 'absolute', right: 10, display: 'flex', color: 'var(--text-3)', pointerEvents: 'none' }}>
          <Icon name="chevron-down" size={14} />
        </span>
      </span>
    </label>
  );
}
