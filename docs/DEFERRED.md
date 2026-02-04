# Deferred Items

Tracking low-priority gaps and technical debt identified during development. Items here are acknowledged but not blocking the v0 spine.

## Intake (Step 1)

### Low Priority

| Item | Rationale | Owner |
|------|-----------|-------|
| **Acceptance criteria minimum validation** | Empty list is valid - worker can still execute. Add policy rule requiring ≥1 criterion if strictness needed. | TBD |
| **Evidence requirements enforcement** | Worker responsibility to validate artifacts exist before marking complete. Not an intake concern. | Worker |

### Technical Debt

| Item | Rationale | Timeline |
|------|-----------|----------|
| **Legacy `TaskCreateLegacyV1` deprecation** | Still in codebase for backward compatibility. Need deprecation timeline and migration path for clients. | V2 |
| **`test_cwom_db_models.py` failures** | Pre-existing: DB model `to_dict()` doesn't return `kind` field. Not blocking functionality. | Backlog |

---

## Completed (moved from deferred)

| Item | Resolution | Date |
|------|------------|------|
| FK constraint `tasks.cwom_issue_id` | Migration `g8b9c0d1e2f3` adds FK with `ON DELETE SET NULL` | 2026-02-04 |
| Task audit logging | `AuditService.log_create()` called in `/tasks/enqueue` | 2026-02-04 |
| Cascade delete strategy | Handled via `ON DELETE SET NULL` - task keeps running if issue deleted | 2026-02-04 |

---

## How to Use This File

1. When identifying gaps during validation/gap analysis, add low-priority items here
2. Include rationale for why it's deferred (not blocking, owner unclear, etc.)
3. Move to "Completed" section when resolved
4. Review periodically to promote items if priorities change
