import React from 'react';
import { Icon } from '../icons/Icon.jsx';

/**
 * Small neutral metadata chip — branch names, policy names, artifact counts.
 * Neutral by design; use Badge when the value carries status.
 */
export function Tag({ icon, mono = false, onRemove, style, children }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '5px',
      padding: '2px 8px',
      background: 'rgba(255,255,255,0.05)', color: 'var(--text-2)',
      border: '1px solid var(--border-hairline)',
      borderRadius: '6px',
      fontFamily: mono ? 'var(--font-mono)' : 'var(--font-sans)',
      fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-medium)',
      whiteSpace: 'nowrap',
      ...style,
    }}>
      {icon ? <Icon name={icon} size={12} /> : null}
      {children}
      {onRemove ? (
        <button
          onClick={onRemove}
          aria-label="Remove"
          style={{ display: 'inline-flex', padding: 0, margin: '0 -2px 0 2px', background: 'none', border: 'none', color: 'var(--text-3)', cursor: 'pointer' }}
        >
          <Icon name="x" size={11} />
        </button>
      ) : null}
    </span>
  );
}
