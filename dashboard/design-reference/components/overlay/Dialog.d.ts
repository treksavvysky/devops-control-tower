import { CSSProperties, ReactNode } from 'react';

/**
 * Modal dialog on a heavy-blur scrim; fade-in only, nothing bounces.
 */
export interface DialogProps {
  open?: boolean;
  /** Called on scrim click and close button. */
  onClose?: () => void;
  title?: string;
  subtitle?: string;
  /** Right-aligned action row, e.g. Cancel + Confirm buttons. */
  footer?: ReactNode;
  /** Pixel width. Default 480. */
  width?: number;
  children?: ReactNode;
}
