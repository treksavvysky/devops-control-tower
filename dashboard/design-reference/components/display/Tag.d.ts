import { CSSProperties, ReactNode, MouseEventHandler } from 'react';

/**
 * Small neutral metadata chip — branches, policies, artifact counts.
 */
export interface TagProps {
  /** Optional leading icon name, e.g. "git-branch". */
  icon?: string;
  /** Mono font for IDs, hashes, branch names. */
  mono?: boolean;
  /** Show a remove ✕; called on click. */
  onRemove?: MouseEventHandler;
  style?: CSSProperties;
  children?: ReactNode;
}
