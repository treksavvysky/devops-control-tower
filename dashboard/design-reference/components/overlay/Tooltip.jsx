import React, { useState } from 'react';

/**
 * Hover tooltip — small dark panel above the wrapped element.
 */
export function Tooltip({ content, side = 'top', style, children }) {
  const [show, setShow] = useState(false);
  const pos = side === 'bottom'
    ? { top: 'calc(100% + 8px)' }
    : { bottom: 'calc(100% + 8px)' };
  return (
    <span
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
      style={{ position: 'relative', display: 'inline-flex', ...style }}
    >
      {children}
      {show ? (
        <span role="tooltip" style={{
          position: 'absolute', left: '50%', transform: 'translateX(-50%)', ...pos,
          zIndex: 1100, whiteSpace: 'nowrap',
          padding: '5px 10px',
          background: '#1c2029',
          border: '1px solid var(--border-strong)',
          borderRadius: 'var(--radius-sm)',
          boxShadow: 'var(--shadow-raised)',
          fontFamily: 'var(--font-sans)', fontSize: 'var(--text-xs)',
          fontWeight: 'var(--weight-medium)', color: 'var(--text-1)',
          animation: 'dct-fade-in var(--duration-fast) var(--ease-out)',
        }}>
          {content}
        </span>
      ) : null}
    </span>
  );
}
