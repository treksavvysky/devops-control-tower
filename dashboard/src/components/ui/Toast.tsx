import type { CSSProperties, ReactNode } from 'react';
import { Icon, type IconName } from '@/components/icons/Icon';
import { IconButton } from './IconButton';

type ToastKind = 'info' | 'success' | 'warning' | 'error';

const KIND_ICONS: Record<ToastKind, IconName> = {
  info: 'info',
  success: 'circle-check',
  warning: 'triangle-alert',
  error: 'circle-x',
};

interface ToastProps {
  kind?: ToastKind;
  title?: ReactNode;
  description?: ReactNode;
  onDismiss?: () => void;
  className?: string;
  style?: CSSProperties;
}

/**
 * Toast / inline callout — glass panel with a semantic tint stripe.
 * Render inside a fixed container for toasts, or inline as a callout.
 */
export function Toast({ kind = 'info', title, description, onDismiss, className, style }: ToastProps) {
  const cls = ['dct-toast', `dct-toast--${kind}`, className].filter(Boolean).join(' ');
  return (
    <div className={cls} style={style}>
      <span className="dct-toast__icon">
        <Icon name={KIND_ICONS[kind]} size={15} />
      </span>
      <div className="dct-toast__content">
        {title ? <div className="dct-toast__title">{title}</div> : null}
        {description ? <div className="dct-toast__description">{description}</div> : null}
      </div>
      {onDismiss ? <IconButton icon="x" label="Dismiss" variant="ghost" size="sm" onClick={onDismiss} /> : null}
    </div>
  );
}
