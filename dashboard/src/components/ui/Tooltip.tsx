import type { CSSProperties, ReactNode } from 'react';

interface TooltipProps {
  content: ReactNode;
  side?: 'top' | 'bottom';
  className?: string;
  style?: CSSProperties;
  children: ReactNode;
}

/** Hover tooltip — small dark panel above (or below) the wrapped element. */
export function Tooltip({ content, side = 'top', className, style, children }: TooltipProps) {
  return (
    <span className={['dct-tooltip-wrap', className].filter(Boolean).join(' ')} style={style}>
      {children}
      <span role="tooltip" className={`dct-tooltip dct-tooltip--${side}`}>
        {content}
      </span>
    </span>
  );
}
