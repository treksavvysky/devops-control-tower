import { CSSProperties } from 'react';

/**
 * Native select styled as an inset dark well with chevron.
 */
export interface SelectProps {
  /** Small uppercase label above the field. */
  label?: string;
  /** Option strings or { value, label } objects. */
  options: Array<string | { value: string; label: string }>;
  value?: string;
  onChange?: (e: any) => void;
  disabled?: boolean;
  style?: CSSProperties;
  selectStyle?: CSSProperties;
}
