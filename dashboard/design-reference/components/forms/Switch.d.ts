import { CSSProperties } from 'react';

/**
 * Toggle switch — blue gradient track with soft glow when on.
 */
export interface SwitchProps {
  checked?: boolean;
  /** Called with the new boolean value. */
  onChange?: (checked: boolean) => void;
  label?: string;
  disabled?: boolean;
  style?: CSSProperties;
}
