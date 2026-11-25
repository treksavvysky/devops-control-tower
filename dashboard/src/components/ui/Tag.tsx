import type { CSSProperties, MouseEventHandler, ReactNode } from 'react';
import { Icon, type IconName } from '@/components/icons/Icon';

interface TagProps {
  icon?: IconName;
  /** Mono type for branch names, run IDs, hashes. */
  mono?: boolean;
  onRemove?: MouseEventHandler<HTMLButtonElement>;
  className?: string;
  style?: CSSProperties;
  children: ReactNode;
}

/**
 * Small neutral metadata chip — branch names, policy names, artifact counts.
 * Neutral by design; use Badge when the value carries status.
 */
export function Tag({ icon, mono = false, onRemove, className, style, children }: TagProps) {
  const cls = ['dct-tag', mono && 'dct-tag--mono', className].filter(Boolean).join(' ');
  return (
    <span className={cls} style={style}>
      {icon ? <Icon name={icon} size={12} /> : null}
      {children}
      {onRemove ? (
        <button type="button" className="dct-tag__remove" onClick={onRemove} aria-label="Remove">
          <Icon name="x" size={11} />
        </button>
      ) : null}
    </span>
  );
}
