import { ReactNode, CSSProperties } from 'react';

/**
 * Line icon from the DCT icon set (Lucide, 2px stroke). Inherits currentColor.
 * @startingPoint section="Primitives" subtitle="Lucide line icons, semantic colors via currentColor" viewport="700x150"
 */
export interface IconProps {
  /** Icon name, e.g. "activity", "shield-check", "circle-x". See Icon.names for the full set. */
  name: string;
  /** Pixel size. Default 16. */
  size?: number;
  /** Stroke width. Default 2. */
  strokeWidth?: number;
  style?: CSSProperties;
}
