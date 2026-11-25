import React, { useState } from 'react';
import { Icon } from '../icons/Icon.jsx';

const VARIANTS = {
  primary: { background: 'var(--grad-blue)', color: 'var(--text-on-accent)', border: '1px solid rgba(255,255,255,0.12)', glow: 'var(--glow-blue)' },
  success: { background: 'var(--grad-green)', color: 'var(--text-on-accent)', border: '1px solid rgba(255,255,255,0.12)', glow: 'var(--glow-green)' },
  danger: { background: 'var(--grad-red)', color: 'var(--text-on-accent)', border: '1px solid rgba(255,255,255,0.12)', glow: 'var(--glow-red)' },
  secondary: { background: 'var(--surface-glass-2)', color: 'var(--text-1)', border: '1px solid var(--border-hairline)', glow: 'none' },
  ghost: { background: 'transparent', color: 'var(--text-2)', border: '1px solid transparent', glow: 'none' },
};

const SIZES = {
  sm: { padding: '6px 12px', fontSize: 'var(--text-sm)', iconSize: 14 },
  md: { padding: '9px 16px', fontSize: 'var(--text-sm)', iconSize: 15 },
  lg: { padding: '12px 22px', fontSize: 'var(--text-base)', iconSize: 16 },
};

/**
 * DCT action button. Gradient fills with a faint colored glow for the three
 * semantic actions; glass secondary and quiet ghost for everything else.
 */
export function Button({ variant = 'primary', size = 'md', icon, disabled = false, onClick, style, children, ...rest }) {
  const [hover, setHover] = useState(false);
  const v = VARIANTS[variant] || VARIANTS.primary;
  const s = SIZES[size] || SIZES.md;
  return (
    <button
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: '8px',
        padding: s.padding, fontSize: s.fontSize,
        fontFamily: 'var(--font-sans)', fontWeight: 'var(--weight-semibold)',
        color: v.color, background: v.background, border: v.border,
        borderRadius: 'var(--radius-md)', cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.45 : 1,
        boxShadow: !disabled && hover && v.glow !== 'none' ? v.glow : 'none',
        filter: !disabled && hover ? 'brightness(1.08)' : 'none',
        transition: 'box-shadow var(--duration-fast) var(--ease-out), filter var(--duration-fast) var(--ease-out), background var(--duration-fast) var(--ease-out)',
        ...(variant === 'ghost' && hover && !disabled ? { background: 'var(--surface-glass-2)', color: 'var(--text-1)' } : {}),
        ...style,
      }}
      {...rest}
    >
      {icon ? <Icon name={icon} size={s.iconSize} /> : null}
      {children}
    </button>
  );
}
