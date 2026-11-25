import type { CSSProperties, InputHTMLAttributes, TextareaHTMLAttributes } from 'react';
import { Icon, type IconName } from '@/components/icons/Icon';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  /** Leading icon inside the well. */
  icon?: IconName;
  /** Error message; also paints the border red. */
  error?: string;
  /** Mono type for IDs, hashes, branch names. */
  mono?: boolean;
  wrapClassName?: string;
  wrapStyle?: CSSProperties;
}

/** Text input on an inset dark well with a hairline border; blue focus ring. */
export function Input({
  label,
  icon,
  error,
  mono = false,
  className,
  wrapClassName,
  wrapStyle,
  ...rest
}: InputProps) {
  const inputCls = [
    'dct-input',
    icon && 'dct-input--with-icon',
    mono && 'dct-input--mono',
    error && 'dct-input--error',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <label className={['dct-field', wrapClassName].filter(Boolean).join(' ')} style={wrapStyle}>
      {label ? <span className="dct-field__label">{label}</span> : null}
      <span className="dct-field__wrap">
        {icon ? (
          <span className="dct-field__icon">
            <Icon name={icon} size={15} />
          </span>
        ) : null}
        <input className={inputCls} {...rest} />
      </span>
      {error ? (
        <span className="dct-field__error">
          <Icon name="triangle-alert" size={12} /> {error}
        </span>
      ) : null}
    </label>
  );
}

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  wrapClassName?: string;
  wrapStyle?: CSSProperties;
}

/** Multi-line input on the same inset well (DCT extension of Input). */
export function Textarea({ label, className, wrapClassName, wrapStyle, ...rest }: TextareaProps) {
  return (
    <label className={['dct-field', wrapClassName].filter(Boolean).join(' ')} style={wrapStyle}>
      {label ? <span className="dct-field__label">{label}</span> : null}
      <textarea className={['dct-textarea', className].filter(Boolean).join(' ')} {...rest} />
    </label>
  );
}
