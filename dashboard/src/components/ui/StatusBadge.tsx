import { Badge } from './Badge';
import { statusBadge, statusLabel } from '@/lib/status';

interface StatusBadgeProps {
  /** A CWOM status, verdict, or decision (e.g. "under_review", "pass"). */
  status?: string | null;
  /** Override the auto-generated label. */
  label?: string;
  /** Leading dot; pulses when the status is "running". */
  dot?: boolean;
}

/** Renders any CWOM status/verdict with its canonical badge color. */
export function StatusBadge({ status, label, dot = false }: StatusBadgeProps) {
  const mapped = statusBadge(status);
  return (
    <Badge status={mapped} dot={dot} pulse={dot && mapped === 'running'}>
      {label ?? statusLabel(status)}
    </Badge>
  );
}
