import { CSSProperties } from 'react';

/**
 * Text input on an inset dark well; blue focus ring, red error state.
 */
export interface InputProps {
  /** Small uppercase label above the field. */
  label?: string;
  /** Optional leading icon name, e.g. "search". */
  icon?: string;
  /** Error message; shows red border + message below. */
  error?: string;
  /** Use the mono font (run IDs, hashes, commands). */
  mono?: boolean;
  placeholder?: string;
  value?: string;
  onChange?: (e: any) => void;
  disabled?: boolean;
  type?: string;
  style?: CSSProperties;
  inputStyle?: CSSProperties;
}
