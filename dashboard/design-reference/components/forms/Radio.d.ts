import { CSSProperties } from 'react';

/**
 * Custom radio — blue ring with inner dot when selected.
 */
export interface RadioProps {
  checked?: boolean;
  /** Called with this radio's value when selected. */
  onChange?: (value: string) => void;
  label?: string;
  name?: string;
  value?: string;
  disabled?: boolean;
  style?: CSSProperties;
}
