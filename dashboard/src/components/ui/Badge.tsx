import type { CSSProperties, ReactNode } from 'react';

export type BadgeStatus = 'running' | 'approved' | 'pending' | 'rejected' | 'neutral';

interface BadgeProps {
  status?: BadgeStatus;
  /** Leading status dot in the accent color. */
  dot?: boolean;
  /** Pulse the dot — only for genuinely live states. */
  pulse?: boolean;
  className?: string;
  style?: CSSProperties;
  children: ReactNode;
}

/**
 * Pill-shaped uppercase status badge. Status is strictly semantic:
 * running=blue, approved=green, pending=amber, rejected=red.
 */
export function Badge({
  status = 'neutral',
  dot = false,
  pulse = false,
  className,
  style,
  children,
}: BadgeProps) {
  const cls = ['dct-badge', `dct-badge--${status}`, className].filter(Boolean).join(' ');
  return (
    <span className={cls} style={style}>
      {dot ? (
        <span className={`dct-badge__dot${pulse ? ' dct-badge__dot--pulse' : ''}`} />
      ) : null}
      {children}
    </span>
  );
}
