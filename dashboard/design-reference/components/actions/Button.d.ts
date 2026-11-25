import { CSSProperties, ReactNode, MouseEventHandler } from 'react';

/**
 * DCT action button — gradient fill + faint glow for semantic actions (primary/success/danger),
 * glass secondary, quiet ghost.
 * @startingPoint section="Primitives" subtitle="Gradient action buttons with semantic glow" viewport="700x220"
 */
export interface ButtonProps {
  /** primary = blue action, success = approve, danger = reject, secondary = glass, ghost = quiet. Default "primary". */
  variant?: 'primary' | 'success' | 'danger' | 'secondary' | 'ghost';
  /** Default "md". */
  size?: 'sm' | 'md' | 'lg';
  /** Optional leading icon name from the DCT icon set, e.g. "check", "play". */
  icon?: string;
  disabled?: boolean;
  onClick?: MouseEventHandler;
  style?: CSSProperties;
  children?: ReactNode;
}
