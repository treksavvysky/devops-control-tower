import type { CSSProperties, MouseEventHandler, ReactNode } from 'react';

interface CardProps {
  title?: ReactNode;
  subtitle?: ReactNode;
  /** Right-aligned header slot (buttons, badges). */
  action?: ReactNode;
  /** Lifts 2px on hover; use for cards that navigate or open something. */
  interactive?: boolean;
  onClick?: MouseEventHandler<HTMLDivElement>;
  /** CSS padding value; defaults to var(--space-5). */
  padding?: string;
  className?: string;
  style?: CSSProperties;
  children?: ReactNode;
}

/**
 * Frosted glass panel — the base surface of every DCT view.
 * Interactive cards lift 2px on hover; static cards never move.
 */
export function Card({
  title,
  subtitle,
  action,
  interactive = false,
  onClick,
  padding = 'var(--space-5)',
  className,
  style,
  children,
}: CardProps) {
  const cls = ['dct-card', interactive && 'dct-card--interactive', className]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={cls} onClick={onClick} style={{ padding, ...style }}>
      {title || action ? (
        <div className={`dct-card__header${children ? ' dct-card__header--with-body' : ''}`}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {title ? <div className="dct-card__title">{title}</div> : null}
            {subtitle ? <div className="dct-card__subtitle">{subtitle}</div> : null}
          </div>
          {action ? <div style={{ flexShrink: 0 }}>{action}</div> : null}
        </div>
      ) : null}
      {children}
    </div>
  );
}
