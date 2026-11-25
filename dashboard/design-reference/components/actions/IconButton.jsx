import React, { useState } from 'react';
import { Icon } from '../icons/Icon.jsx';

/**
 * Square glass icon button for toolbars, table rows, and panel headers.
 */
export function IconButton({ icon, label, variant = 'glass', size = 'md', disabled = false, onClick, style, ...rest }) {
  const [hover, setHover] = useState(false);
  const dim = size === 'sm' ? 28 : size === 'lg' ? 40 : 34;
  const iconSize = size === 'sm' ? 14 : size === 'lg' ? 18 : 16;
  const isGhost = variant === 'ghost';
  const isDanger = variant === 'danger';
  return (
    <button
      aria-label={label}
      title={label}
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        width: dim, height: dim, padding: 0,
        background: isGhost && !hover ? 'transparent' : hover && !disabled ? 'var(--surface-glass-2)' : isGhost ? 'transparent' : 'var(--surface-glass)',
        border: isGhost ? '1px solid transparent' : '1px solid var(--border-hairline)',
        borderRadius: 'var(--radius-sm)',
        color: isDanger ? 'var(--accent-red)' : hover && !disabled ? 'var(--text-1)' : 'var(--text-2)',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.45 : 1,
        transition: 'background var(--duration-fast) var(--ease-out), color var(--duration-fast) var(--ease-out)',
        ...style,
      }}
      {...rest}
    >
      <Icon name={icon} size={iconSize} />
    </button>
  );
}
