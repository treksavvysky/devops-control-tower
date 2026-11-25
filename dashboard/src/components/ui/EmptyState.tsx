import type { ReactNode } from 'react';
import { Card } from './Card';
import { Icon, type IconName } from '@/components/icons/Icon';

interface EmptyStateProps {
  icon?: IconName;
  title: string;
  description?: string;
  action?: ReactNode;
}

/** Centered empty message on a glass card. */
export function EmptyState({ icon = 'circle-check', title, description, action }: EmptyStateProps) {
  return (
    <Card padding="var(--space-12)" className="text-center">
      <div className="text-muted mb-4" style={{ display: 'flex', justifyContent: 'center' }}>
        <Icon name={icon} size={28} />
      </div>
      <div className="dct-card__title mb-2">{title}</div>
      {description ? <p className="text-sm text-secondary" style={{ margin: 0 }}>{description}</p> : null}
      {action ? <div className="mt-4" style={{ display: 'flex', justifyContent: 'center' }}>{action}</div> : null}
    </Card>
  );
}
