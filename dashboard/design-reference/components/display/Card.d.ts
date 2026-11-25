import { CSSProperties, ReactNode, MouseEventHandler } from 'react';

/**
 * Frosted glass panel — the base surface of every DCT view. 16px radius,
 * hairline border, layered shadow. Interactive cards lift on hover.
 * @startingPoint section="Primitives" subtitle="Frosted glass panel, the base DCT surface" viewport="700x260"
 */
export interface CardProps {
  /** Header title (17px semibold). */
  title?: string;
  /** Secondary line under the title. */
  subtitle?: string;
  /** Right-aligned header slot — badge, button, icon button. */
  action?: ReactNode;
  /** Hover lift + pointer; use only when the card navigates. */
  interactive?: boolean;
  onClick?: MouseEventHandler;
  /** CSS padding. Default var(--space-5). */
  padding?: string;
  style?: CSSProperties;
  children?: ReactNode;
}
