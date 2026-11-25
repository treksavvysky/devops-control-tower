'use client';

import type { ReactNode } from 'react';
import { IconButton } from './IconButton';

interface DialogProps {
  open?: boolean;
  onClose?: () => void;
  title?: ReactNode;
  subtitle?: ReactNode;
  /** Right-aligned action row under a hairline divider. */
  footer?: ReactNode;
  /** Panel width in px. */
  width?: number;
  children?: ReactNode;
}

/** Modal dialog on a heavy-blur scrim. Calm entrance (fade only). */
export function Dialog({ open = false, onClose, title, subtitle, footer, width = 480, children }: DialogProps) {
  if (!open) return null;
  return (
    <div className="dct-dialog-scrim" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        className="dct-dialog"
        style={{ width }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="dct-dialog__header">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {title ? <div className="dct-dialog__title">{title}</div> : null}
            {subtitle ? <div className="dct-dialog__subtitle">{subtitle}</div> : null}
          </div>
          <IconButton icon="x" label="Close" variant="ghost" size="sm" onClick={onClose} />
        </div>
        <div className="dct-dialog__body">{children}</div>
        {footer ? <div className="dct-dialog__footer">{footer}</div> : null}
      </div>
    </div>
  );
}
