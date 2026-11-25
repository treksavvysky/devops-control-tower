import type { CSSProperties, ReactNode } from 'react';

export type StatAccent = 'blue' | 'green' | 'amber' | 'red' | 'neutral';

interface StatProps {
  label: string;
  value: ReactNode;
  /** Must match the number's meaning (green = good, red = failing…). */
  accent?: StatAccent;
  /** Small caption under the value. */
  detail?: ReactNode;
  className?: string;
  style?: CSSProperties;
}

/**
 * Big confident stat — 2.5rem bold number in an accent color over a small
 * uppercase label.
 */
export function Stat({ label, value, accent = 'neutral', detail, className, style }: StatProps) {
  const cls = ['dct-stat', className].filter(Boolean).join(' ');
  return (
    <div className={cls} style={style}>
      <span className="dct-stat__label">{label}</span>
      <span className={`dct-stat__value dct-stat__value--${accent}`}>{value}</span>
      {detail ? <span className="dct-stat__detail">{detail}</span> : null}
    </div>
  );
}
