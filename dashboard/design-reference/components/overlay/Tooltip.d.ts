import { CSSProperties, ReactNode } from 'react';

/**
 * Hover tooltip — small dark panel above (or below) the wrapped element.
 */
export interface TooltipProps {
  /** Tooltip text. */
  content: ReactNode;
  side?: 'top' | 'bottom';
  style?: CSSProperties;
  children?: ReactNode;
}
