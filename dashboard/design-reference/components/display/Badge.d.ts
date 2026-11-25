import { CSSProperties, ReactNode } from 'react';

/**
 * Pill-shaped uppercase status badge — 15% tint + matching border.
 * Status colors are strictly semantic.
 * @startingPoint section="Primitives" subtitle="Uppercase status pills, strictly semantic colors" viewport="700x150"
 */
export interface BadgeProps {
  /** running=blue, approved=green, pending=amber, rejected=red, neutral=gray. */
  status?: 'running' | 'approved' | 'pending' | 'rejected' | 'neutral';
  /** Show a leading status dot. */
  dot?: boolean;
  /** Pulse the dot (live/running states only). */
  pulse?: boolean;
  style?: CSSProperties;
  children?: ReactNode;
}
