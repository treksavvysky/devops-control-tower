import type { ButtonHTMLAttributes } from 'react';
import { Icon, type IconName } from '@/components/icons/Icon';

type IconButtonVariant = 'glass' | 'ghost' | 'danger';
type IconButtonSize = 'sm' | 'md' | 'lg';

const ICON_SIZES: Record<IconButtonSize, number> = { sm: 14, md: 16, lg: 18 };

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  icon: IconName;
  /** Accessible name — required, this button has no text. */
  label: string;
  variant?: IconButtonVariant;
  size?: IconButtonSize;
}

/** Square glass icon button for toolbars, table rows, and panel headers. */
export function IconButton({
  icon,
  label,
  variant = 'glass',
  size = 'md',
  className,
  ...rest
}: IconButtonProps) {
  const cls = [
    'dct-iconbtn',
    `dct-iconbtn--${size}`,
    variant !== 'glass' && `dct-iconbtn--${variant}`,
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <button aria-label={label} title={label} className={cls} {...rest}>
      <Icon name={icon} size={ICON_SIZES[size]} />
    </button>
  );
}
