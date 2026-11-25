import { CSSProperties } from 'react';

/**
 * Underline tabs with blue active indicator; optional count pills.
 */
export interface TabsProps {
  /** Tab strings or { value, label, count? } objects. */
  tabs: Array<string | { value: string; label: string; count?: number }>;
  /** Controlled active value. */
  value?: string;
  /** Uncontrolled initial value (defaults to first tab). */
  defaultValue?: string;
  onChange?: (value: string) => void;
  style?: CSSProperties;
}
