import type { CSSProperties } from 'react';
import { ICON_DATA, ICON_NAMES, type IconName } from './icon-data';

interface IconProps {
  name: IconName;
  /** Rendered width/height in px. */
  size?: number;
  strokeWidth?: number;
  className?: string;
  style?: CSSProperties;
  /** Accessible label; icons are decorative (aria-hidden) by default. */
  label?: string;
}

/**
 * DCT icon — Lucide glyphs rendered inline so they stroke with currentColor.
 * Color comes from the surrounding text color; size defaults to 16.
 */
export function Icon({ name, size = 16, strokeWidth = 2, className, style, label }: IconProps) {
  const data = ICON_DATA[name];
  if (!data) return null;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      style={{ flexShrink: 0, ...style }}
      aria-hidden={label ? undefined : true}
      role={label ? 'img' : undefined}
      aria-label={label}
      dangerouslySetInnerHTML={{ __html: data }}
    />
  );
}

Icon.names = ICON_NAMES;

export type { IconName };
