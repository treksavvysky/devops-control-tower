import { CSSProperties } from 'react';

/**
 * Custom checkbox — blue fill with white check when on.
 */
export interface CheckboxProps {
  checked?: boolean;
  /** Called with the new boolean value. */
  onChange?: (checked: boolean) => void;
  label?: string;
  disabled?: boolean;
  style?: CSSProperties;
}
