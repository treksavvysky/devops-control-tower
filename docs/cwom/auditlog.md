No—AuditLog isn’t a new “CWOM core” model. It’s an optional supporting table that records who changed what, when, and why across the CWOM objects.

In CWOM v0.1, the canonical objects are the 7 you listed:
Repo, Issue, ContextPacket, Run, Artifact, ConstraintSnapshot, DoctrineRef.

AuditLog is a pragmatic add-on because it gives you immediate operational superpowers:

What AuditLog is

A single append-only record type like:
	•	timestamp: when the change happened
	•	actor: human/agent/system that caused it
	•	action: created / updated / status_changed / linked / unlinked
	•	entity: kind + id (e.g., Issue 01HZ…)
	•	before / after: JSON snapshots (or a patch/diff)
	•	note: optional reason (e.g., “auto-transition after tests passed”)

How it fits the larger picture

AuditLog is the bridge between:
	•	“CWOM as current state tables” and
	•	“CWOM as a full event-sourced timeline” (which you may want later)

It also becomes your black box flight recorder for debugging agents:
	•	Why did Run 128 fail?
	•	Which doctrine version was used?
	•	Who flipped Issue from blocked to ready?
	•	What changed right before production went sideways?

Why it’s worth adding early
	•	Cheap now, expensive later: once multiple agents/services are writing CWOM, retrofitting provenance is painful.
	•	Debuggability: turns “mysterious behavior” into traceable causality.
	•	Compliance/safety: policy enforcement becomes inspectable.

If you want it to remain “non-core”

Mark it as:
	•	CWOM v0.1 core = 7 objects
	•	CWOM adjunct = AuditLog

So: not a new core model, but a smart “instrumentation layer” you’ll be glad you installed before the system starts moving fast.