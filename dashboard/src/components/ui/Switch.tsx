'use client';

import type { CSSProperties, ReactNode } from 'react';

interface SwitchProps {
  checked?: boolean;
  onChange?: (checked: boolean) => void;
  label?: ReactNode;
  disabled?: boolean;
  className?: string;
  style?: CSSProperties;
}

/** Toggle switch — blue gradient track when on, gentle slide. */
export function Switch({ checked = false, onChange, label, disabled = false, className, style }: SwitchProps) {
  const cls = ['dct-check', disabled && 'dct-check--disabled', className].filter(Boolean).join(' ');
  return (
    <label className={cls} style={{ gap: 10, ...style }}>
      <input
        type="checkbox"
        role="switch"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange?.(e.target.checked)}
      />
      <span className="dct-switch__track">
        <span className="dct-switch__thumb" />
      </span>
      {label ? <span className="dct-check__label">{label}</span> : null}
    </label>
  );
}
