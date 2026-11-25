import { Badge, Button, Card, PageHeader, Stat } from '@/components/ui';

export default function Home() {
  return (
    <div>
      <PageHeader
        title="Command center"
        subtitle="Monitor system health and pending agent tasks."
      />

      <div className="stack-5">
        <Card>
          <div className="grid-cols-3">
            <Stat
              label="Active agents"
              value={12}
              accent="blue"
              detail="Running in isolated contexts"
            />
            <Stat
              label="Pending reviews"
              value="—"
              accent="amber"
              detail={
                <Button href="/reviews" variant="secondary" size="sm" icon="eye">
                  Open review queue
                </Button>
              }
            />
            <Stat
              label="Tasks completed"
              value="1,432"
              accent="green"
              detail="In the last 7 days"
            />
          </div>
        </Card>

        <Card
          title="Recent activity"
          subtitle="Streaming from all agents"
          action={<Badge status="running" dot pulse>Live</Badge>}
        >
          <p className="text-sm text-muted" style={{ margin: 0 }}>
            Orchestrator log streaming goes here.
          </p>
        </Card>
      </div>
    </div>
  );
}
