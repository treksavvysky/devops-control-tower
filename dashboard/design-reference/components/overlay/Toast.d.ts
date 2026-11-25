import { CSSProperties } from 'react';

/**
 * Toast / inline callout — glass panel with semantic icon chip.
 */
export interface ToastProps {
  /** info=blue, success=green, warning=amber, error=red. */
  kind?: 'info' | 'success' | 'warning' | 'error';
  title?: string;
  description?: string;
  /** Shows a dismiss ✕ when provided. */
  onDismiss?: () => void;
  style?: CSSProperties;
}
