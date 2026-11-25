import type { CSSProperties, SelectHTMLAttributes } from 'react';
import { Icon } from '@/components/icons/Icon';

type SelectOption = string | { value: string; label: string };

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  options?: SelectOption[];
  wrapClassName?: string;
  wrapStyle?: CSSProperties;
}

/** Native select styled as an inset dark well with a chevron affordance. */
export function Select({
  label,
  options = [],
  className,
  wrapClassName,
  wrapStyle,
  ...rest
}: SelectProps) {
  return (
    <label className={['dct-field', wrapClassName].filter(Boolean).join(' ')} style={wrapStyle}>
      {label ? <span className="dct-field__label">{label}</span> : null}
      <span className="dct-field__wrap">
        <select className={['dct-select', className].filter(Boolean).join(' ')} {...rest}>
          {options.map((o) => {
            const opt = typeof o === 'string' ? { value: o, label: o } : o;
            return (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            );
          })}
        </select>
        <span className="dct-select__chevron">
          <Icon name="chevron-down" size={14} />
        </span>
      </span>
    </label>
  );
}
