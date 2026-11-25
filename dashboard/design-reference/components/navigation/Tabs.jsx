import React, { useState } from 'react';

/**
 * Underline tabs for switching panel views. Controlled via value/onChange
 * or uncontrolled with defaultValue.
 */
export function Tabs({ tabs = [], value, defaultValue, onChange, style }) {
  const [internal, setInternal] = useState(defaultValue ?? (tabs[0] && (typeof tabs[0] === 'string' ? tabs[0] : tabs[0].value)));
  const active = value !== undefined ? value : internal;
  const select = (v) => {
    if (value === undefined) setInternal(v);
    if (onChange) onChange(v);
  };
  return (
    <div style={{ display: 'flex', gap: '4px', borderBottom: '1px solid var(--border-hairline)', fontFamily: 'var(--font-sans)', ...style }}>
      {tabs.map((t) => {
        const tab = typeof t === 'string' ? { value: t, label: t } : t;
        const isActive = tab.value === active;
        return (
          <button
            key={tab.value}
            onClick={() => select(tab.value)}
            style={{
              padding: '10px 14px', marginBottom: '-1px',
              background: 'none', border: 'none',
              borderBottom: `2px solid ${isActive ? 'var(--accent-blue)' : 'transparent'}`,
              color: isActive ? 'var(--text-1)' : 'var(--text-2)',
              fontFamily: 'var(--font-sans)', fontSize: 'var(--text-sm)',
              fontWeight: 'var(--weight-medium)', cursor: 'pointer',
              transition: 'color var(--duration-fast) var(--ease-out), border-color var(--duration-fast) var(--ease-out)',
            }}
          >
            {tab.label}
            {tab.count !== undefined ? (
              <span style={{ marginLeft: '7px', padding: '1px 7px', borderRadius: 'var(--radius-pill)', background: 'rgba(255,255,255,0.07)', fontSize: 'var(--text-xs)', color: 'var(--text-3)' }}>
                {tab.count}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
