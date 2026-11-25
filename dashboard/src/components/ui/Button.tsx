import Link from 'next/link';
import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { Icon, type IconName } from '@/components/icons/Icon';

export type ButtonVariant = 'primary' | 'success' | 'danger' | 'secondary' | 'ghost';
export type ButtonSize = 'sm' | 'md' | 'lg';

const ICON_SIZES: Record<ButtonSize, number> = { sm: 14, md: 15, lg: 16 };

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Leading Lucide icon. */
  icon?: IconName;
  /** Renders a Next.js <Link> styled as a button. */
  href?: string;
  /** Full-width button. */
  block?: boolean;
  children?: ReactNode;
}

/**
 * DCT action button. Gradient fills with a faint colored glow for the three
 * semantic actions; glass secondary and quiet ghost for everything else.
 */
export function Button({
  variant = 'primary',
  size = 'md',
  icon,
  href,
  block = false,
  className,
  children,
  ...rest
}: ButtonProps) {
  const cls = [
    'dct-btn',
    `dct-btn--${variant}`,
    `dct-btn--${size}`,
    block && 'dct-btn--block',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  const content = (
    <>
      {icon ? <Icon name={icon} size={ICON_SIZES[size]} /> : null}
      {children}
    </>
  );

  if (href) {
    return (
      <Link href={href} className={cls}>
        {content}
      </Link>
    );
  }

  return (
    <button className={cls} {...rest}>
      {content}
    </button>
  );
}
