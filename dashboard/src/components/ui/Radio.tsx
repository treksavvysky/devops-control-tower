'use client';

import type { CSSProperties, ReactNode } from 'react';

interface RadioProps {
  checked?: boolean;
  onChange?: (value: string) => void;
  label?: ReactNode;
  name?: string;
  value: string;
  disabled?: boolean;
  className?: string;
  style?: CSSProperties;
}

/** Custom radio — blue ring with inner dot when selected. */
export function Radio({
  checked = false,
  onChange,
  label,
  name,
  value,
  disabled = false,
  className,
  style,
}: RadioProps) {
  const cls = ['dct-check', disabled && 'dct-check--disabled', className].filter(Boolean).join(' ');
  return (
    <label className={cls} style={style}>
      <input
        type="radio"
        checked={checked}
        name={name}
        value={value}
        disabled={disabled}
        onChange={() => onChange?.(value)}
      />
      <span className="dct-radio__ring">
        <span className="dct-radio__dot" />
      </span>
      {label ? <span className="dct-check__label">{label}</span> : null}
    </label>
  );
}
