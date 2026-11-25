import { CSSProperties, MouseEventHandler } from 'react';

/**
 * Square glass icon button for toolbars, table rows, and panel headers.
 */
export interface IconButtonProps {
  /** Icon name from the DCT icon set. */
  icon: string;
  /** Accessible label (also shown as tooltip via title). */
  label: string;
  /** glass = bordered glass (default), ghost = borderless, danger = red icon. */
  variant?: 'glass' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  disabled?: boolean;
  onClick?: MouseEventHandler;
  style?: CSSProperties;
}
