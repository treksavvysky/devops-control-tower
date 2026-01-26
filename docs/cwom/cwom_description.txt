Canonical Work Object Model (CWOM) is the boring-but-essential “wiring standard” for your whole ecosystem. It’s not a product feature. It’s the data contract that makes features, agents, and automation composable instead of turning into a spaghetti museum.

What it is (in detail)

CWOM is a small set of canonical object types with stable IDs and explicit links:
	•	Repo: the work container (codebase, docs base, project boundary).
	•	Issue: the unit of intent (what we want).
	•	Context Packet: the versioned briefing (what we know + assumptions + instructions).
	•	Constraint Snapshot: the operating envelope at a moment (time, money, health, policies, tool limits).
	•	Doctrine Ref: the governing “how we decide / how we work” rules, versioned.
	•	Run: an execution attempt (agent/human/CI doing work) with explicit inputs.
	•	Artifact: an output of a Run (PR, commit, report, dataset, build, link) with verification.

The model is intentionally underpowered: it doesn’t try to describe everything. It describes the minimum needed to make work trackable, reproducible, and automatable.

The key property: explicit causality
CWOM makes causality first-class:

Issue + Context + Constraints + Doctrine → (a) Run → produces Artifacts

That single chain is the spine of auditability, reproduction, learning, and orchestration.

⸻

How it fits the larger picture

Think ACE/IntelliSwarm / DevOps Control Tower as “brains and hands.” CWOM is the skeleton they share.

1) It’s the universal adapter layer
Right now you have multiple worlds:
	•	GitHub issues/PRs/commits
	•	“General’s Tent” briefings
	•	agent plans and traces
	•	runtime logs, CI runs, deployments
	•	personal constraints (energy, money, health)
	•	doctrine/policies (ACE principles, security rules)

CWOM is how all those worlds become interoperable. Each system maps its objects into CWOM:
	•	GitHub Issue → CWOM Issue
	•	PR/commit → CWOM Artifact
	•	CI job / agent execution → CWOM Run
	•	briefing doc → Context Packet
	•	current state log → Constraint Snapshot
	•	ACE doctrine registry → Doctrine Refs

Once that mapping exists, orchestration doesn’t care where the work came from. It speaks CWOM.

2) It enables multi-agent coordination without chaos
Swarm intelligence fails when agents don’t share a consistent notion of:
	•	what “the task” is
	•	what the inputs are
	•	what constraints apply
	•	what counts as done
	•	what outputs were produced
	•	what decisions were made

CWOM gives agents a shared language. That’s the difference between:
	•	agents “chatting” (high entropy)
and
	•	agents “executing” (low entropy)

3) It makes your system auditable and self-improving
Without CWOM, learning is mushy. With CWOM:
	•	you can correlate failures with constraints (“failed because tool blocked” vs “bad plan”)
	•	you can compare runs and see what changed (context version, doctrine version, constraints)
	•	you can build “playbooks” from successful run patterns
	•	you can compute leverage metrics (output value per time/token/cost)

This is the substrate for “ACE becomes smarter over time” in a concrete, data-driven way.

⸻

Why work on it first

Because everything else depends on it, whether you admit it or not.

If you build agents, UI, automations, or databases before CWOM, you’ll bake in incompatible assumptions and later pay the “integration tax” with interest.

Here’s the brutally practical logic:

1) CWOM prevents schema fragmentation
If you start building features now, each feature invents its own data shape:
	•	task object v1
	•	run record v1
	•	artifact list v1
	•	“briefing” format v1
	•	constraint tracking v1

Six months later you’re writing migration scripts and arguing with yourself about what a “run” even means. CWOM stops that up front.

2) CWOM unlocks parallel development
Once the schema is locked, you can build independently:
	•	ingestion adapters (GitHub → CWOM)
	•	run executor (enqueue/run/trace)
	•	artifact storage
	•	doctrine registry
	•	constraint capture UI
	•	analytics

Without CWOM, every team/agent blocks on “how do we represent X?”

3) CWOM is how you get determinism and reproducibility
Agent systems go off the rails when they rely on ambient context. CWOM forces explicit inputs:
	•	which context packet was used?
	•	which constraints applied?
	•	which doctrine version governed?
	•	what artifacts resulted?

That’s the minimum viable “scientific method” for agentic work.

4) It’s the leverage multiplier
CWOM is not “more planning.” It’s eliminating rework.

The compounding benefit is that every future capability becomes:
	•	simpler to add
	•	safer to run
	•	easier to debug
	•	easier to automate
	•	easier to improve

⸻

The larger “operating system” view

If you zoom out, your ecosystem has three layers:
	1.	Governance layer
Doctrine Refs + policies + aspiration constraints.
	2.	Orchestration layer (Control Tower / IntelliSwarm Coordinator)
Decides what to run, when, and with which resources.
	3.	Execution layer (agents, CI, humans, sandboxes)
Performs Runs and produces Artifacts.

CWOM sits between governance/orchestration/execution as the shared data plane.

It’s your northbound/southbound bus, but for work itself.

⸻

The real reason (the blunt one)

You’re building a system that must survive scale—more repos, more agents, more tasks, more runs, more failure modes.

CWOM is the difference between:
	•	a clever demo that works in a single chat window
and
	•	an operational machine that can run 60 tasks/day, across 28 repos, with policy enforcement, traceability, and learning.

That machine needs a canonical work substrate. CWOM is that substrate.

Next direction of travel (without asking you questions): define v0.1 JSON Schemas + a tiny reference resolver + a minimal persistence model (Postgres tables matching these objects). That turns CWOM from philosophy into steel.
