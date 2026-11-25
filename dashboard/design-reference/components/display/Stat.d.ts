import { CSSProperties, ReactNode } from 'react';

/**
 * Big confident stat number (2.5rem bold) with uppercase label.
 * Accent color must match the number's meaning.
 */
export interface StatProps {
  /** Small uppercase label above the number. */
  label: string;
  /** The stat value, e.g. "24", "98.2%". */
  value: ReactNode;
  /** blue=running, green=passed, amber=pending, red=failed, neutral=white. */
  accent?: 'blue' | 'green' | 'amber' | 'red' | 'neutral';
  /** Small muted line under the number. */
  detail?: string;
  style?: CSSProperties;
}
