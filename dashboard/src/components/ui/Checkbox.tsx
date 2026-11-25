'use client';

import type { CSSProperties, ReactNode } from 'react';
import { Icon } from '@/components/icons/Icon';

interface CheckboxProps {
  checked?: boolean;
  onChange?: (checked: boolean) => void;
  label?: ReactNode;
  disabled?: boolean;
  className?: string;
  style?: CSSProperties;
}

/** Custom checkbox — blue fill with white check when on. */
export function Checkbox({ checked = false, onChange, label, disabled = false, className, style }: CheckboxProps) {
  const cls = ['dct-check', disabled && 'dct-check--disabled', className].filter(Boolean).join(' ');
  return (
    <label className={cls} style={style}>
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange?.(e.target.checked)}
      />
      <span className="dct-check__box">
        <Icon name="check" size={12} strokeWidth={3} />
      </span>
      {label ? <span className="dct-check__label">{label}</span> : null}
    </label>
  );
}
