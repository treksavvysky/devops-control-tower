'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import type { ReactNode } from 'react';
import { Icon, type IconName } from '@/components/icons/Icon';

interface NavLinkProps {
  href: string;
  icon: IconName;
  /** Amber count pill (e.g. pending reviews). */
  badge?: number;
  children: ReactNode;
}

/** Sidebar nav item with icon, automatic active state, and optional count. */
export function NavLink({ href, icon, badge, children }: NavLinkProps) {
  const pathname = usePathname();
  const active = href === '/' ? pathname === '/' : pathname.startsWith(href);
  return (
    <Link href={href} className={`nav-item${active ? ' active' : ''}`}>
      <Icon name={icon} size={16} />
      <span className="nav-item__label">{children}</span>
      {badge !== undefined ? <span className="nav-item__badge">{badge}</span> : null}
    </Link>
  );
}
