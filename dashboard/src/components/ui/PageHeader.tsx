import type { ReactNode } from 'react';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  /** Mono crumb next to the title (run IDs, hashes). */
  crumb?: string;
  /** Right-aligned actions. */
  actions?: ReactNode;
}

/** Page title with the signature white-to-gray gradient headline. */
export function PageHeader({ title, subtitle, crumb, actions }: PageHeaderProps) {
  return (
    <div className="page-header">
      <div>
        <div className="flex-center flex-gap-3">
          <h1>{title}</h1>
          {crumb ? <code className="mono text-sm text-muted">{crumb}</code> : null}
        </div>
        {subtitle ? <p className="page-subtitle">{subtitle}</p> : null}
      </div>
      {actions ? <div className="flex-gap-2 flex-center">{actions}</div> : null}
    </div>
  );
}
