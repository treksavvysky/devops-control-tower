# Claude Code Executor Roadmap

**Date**: 2026-02-15
**Status**: Planning
**Depends On**: v0 Pipeline (Steps 1-5 Complete)

---

## 1. Overview

Replace `StubExecutor` with a real executor that invokes Claude Code (`claude` CLI) as a subprocess to perform actual task work — code changes, docs, analysis, ops — against a real repo checkout. The executor inherits the existing `Executor` ABC contract so the downstream pipeline (trace, prove, review) remains unchanged.

**Goal**: A queued task with `operation=code_change` results in Claude Code making real edits to a repo worktree, with the diff captured as an artifact, fully traced and auditable.

---

## 2. Architecture

```
WorkerLoop
  │
  ├─ ClaudeCodeExecutor.execute(context, store)
  │     │
  │     ├─ 1. Prepare workspace (git clone/worktree)
  │     ├─ 2. Synthesize prompt (objective + context packet + constraints)
  │     ├─ 3. Invoke `claude -p "<prompt>" --output-format json`
  │     │       with --allowedTools, --max-turns, subprocess timeout
  │     ├─ 4. Collect results (diff, created files, conversation log)
  │     ├─ 5. Write artifacts to TraceStore
  │     └─ 6. Return ExecutionResult (success/fail, artifacts, telemetry)
  │
  ├─ Prover.prove()     # unchanged
  └─ ReviewPolicy       # unchanged
```

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Invocation mode | `claude -p` (print/non-interactive) | Scriptable, returns JSON, no TTY needed |
| Output format | `--output-format json` | Structured result with token usage and tool calls |
| Repo isolation | Git worktree per run | Cheap, parallel-safe, tied to run lifecycle |
| Constraint enforcement | `--allowedTools` allowlist | Maps directly to `allow_network`, `allow_secrets` |
| Time budget | `subprocess.timeout` | Hard kill on budget exceeded |
| Credential isolation | Stripped `env` dict | Executor process gets only what's needed |

---

## 3. Phases

### Phase 1: Workspace Manager

**Goal**: Reliable repo checkout lifecycle for executor runs.

#### 1.1 Create `WorkspaceManager` class

**File**: `devops_control_tower/worker/workspace.py`

Responsibilities:
- `prepare(repo_url, ref, run_id) -> Path` — clone or create git worktree
- `cleanup(run_id)` — remove worktree after execution
- `get_diff(workspace_path) -> str` — capture `git diff` after execution
- `list_new_files(workspace_path) -> list[Path]` — find untracked files

Strategy:
- First run for a repo: `git clone --bare` into a cache dir (`JCT_WORKSPACE_ROOT`)
- Subsequent runs: `git worktree add` from the bare clone
- Cleanup: `git worktree remove` after artifacts collected
- Fallback: full clone if worktrees unavailable

Config additions to `Settings`:
```python
jct_workspace_root: str = Field(
    default="/var/lib/jct/workspaces",
    env="JCT_WORKSPACE_ROOT",
)
jct_workspace_cleanup: bool = Field(
    default=True,
    env="JCT_WORKSPACE_CLEANUP",
)
```

#### 1.2 Tests

**File**: `tests/test_workspace.py`

- Clone into temp dir, verify checkout at ref
- Worktree creation and cleanup
- Diff capture after file modification
- Cleanup removes worktree but not bare repo
- Error handling: invalid repo URL, missing ref

**Estimated effort**: 4h

---

### Phase 2: Prompt Synthesis

**Goal**: Turn `ExecutionContext` into an effective Claude Code prompt.

#### 2.1 Create `PromptBuilder` class

**File**: `devops_control_tower/worker/prompt.py`

Responsibilities:
- `build(context: ExecutionContext) -> str` — synthesize the full prompt
- `build_system_constraints(context) -> str` — constraint instructions
- `build_allowed_tools(context) -> list[str]` — tool allowlist

Prompt structure:
```
## Task
{objective}

## Operation
{operation} on {target_repo} at ref {target_ref}

## Context
{context_packet summary — files, prior decisions, relevant history}

## Constraints
- Time budget: {time_budget_seconds}s
- Network access: {allowed/denied}
- Secrets access: {allowed/denied}
- Scope: {target_path or "full repo"}

## Instructions
- Make only the changes necessary to accomplish the objective
- Do not modify files outside the target path
- Commit your changes with a descriptive message
```

#### 2.2 Tool allowlist mapping

| Constraint | Allowed Tools |
|-----------|---------------|
| Base (always) | Read, Write, Edit, Glob, Grep, Bash (git only) |
| `allow_network=true` | + WebFetch, WebSearch |
| `allow_secrets=true` | + Bash (unrestricted) |
| `operation=analysis` | Read, Glob, Grep only (no Write/Edit) |

#### 2.3 Tests

**File**: `tests/test_prompt_builder.py`

- Prompt includes objective, repo, constraints
- Context packet data injected when present
- Tool allowlist correct for each constraint combination
- Analysis operation restricts to read-only tools

**Estimated effort**: 2h

---

### Phase 3: Claude Code Executor

**Goal**: The executor itself — subprocess invocation and result parsing.

#### 3.1 Create `ClaudeCodeExecutor` class

**File**: `devops_control_tower/worker/claude_executor.py`

```python
class ClaudeCodeExecutor(Executor):
    name = "claude_code"
    version = "0.1.0"

    def __init__(self, workspace_manager: WorkspaceManager):
        self.workspace_manager = workspace_manager
        self.prompt_builder = PromptBuilder()

    def execute(self, context: ExecutionContext, store: TraceStore) -> ExecutionResult:
        # 1. Prepare workspace
        # 2. Build prompt and tool allowlist
        # 3. Invoke claude subprocess
        # 4. Parse JSON response
        # 5. Collect diff and artifacts
        # 6. Write everything to trace store
        # 7. Cleanup workspace
        # 8. Return ExecutionResult
```

#### 3.2 Subprocess invocation

```python
cmd = [
    "claude",
    "-p", prompt,
    "--output-format", "json",
    "--max-turns", str(max_turns),
    "--allowedTools", ",".join(allowed_tools),
]

result = subprocess.run(
    cmd,
    cwd=workspace_path,
    env=sanitized_env,
    capture_output=True,
    timeout=context.time_budget_seconds,
    text=True,
)
```

Key behaviors:
- **Timeout**: `subprocess.TimeoutExpired` → `ExecutionResult(success=False, status="timed_out")`
- **Non-zero exit**: Parse stderr, map to `error_code`/`error_message`
- **Success**: Parse JSON stdout for conversation, token usage, tool calls

#### 3.3 Environment sanitization

The subprocess inherits a **minimal** env dict:
```python
sanitized_env = {
    "HOME": workspace_home,
    "PATH": os.environ["PATH"],
    "ANTHROPIC_API_KEY": api_key,  # Required for Claude Code
    "LANG": "en_US.UTF-8",
}
# Explicitly exclude: DATABASE_URL, SECRET_KEY, REDIS_URL, etc.
```

#### 3.4 Result parsing and artifact collection

After Claude Code finishes:
1. Run `git diff HEAD` in workspace → write as `artifacts/changes.patch`
2. Run `git diff --stat` → write as `artifacts/diff_stat.txt`
3. Copy any new files to `artifacts/` in trace store
4. Write Claude's full JSON response → `artifacts/claude_response.json`
5. Extract conversation → `trace.log` (human-readable)
6. Extract token usage → `ExecutionResult.telemetry`

```python
telemetry = {
    "executor": "claude_code",
    "executor_version": "0.1.0",
    "input_tokens": response["usage"]["input_tokens"],
    "output_tokens": response["usage"]["output_tokens"],
    "total_tokens": response["usage"]["total_tokens"],
    "model": response.get("model"),
    "num_turns": response.get("num_turns"),
    "cost_usd": computed_cost,
}
```

#### 3.5 Register in factory

Update `get_executor()` in `executor.py`:
```python
elif executor_type == "claude_code":
    from .claude_executor import ClaudeCodeExecutor
    from .workspace import WorkspaceManager
    return ClaudeCodeExecutor(WorkspaceManager())
```

#### 3.6 Tests

**File**: `tests/test_claude_executor.py`

- Mock `subprocess.run` — verify command construction, env, timeout
- Parse sample JSON response → correct `ExecutionResult`
- Timeout → `status="timed_out"`
- Non-zero exit → `status="failed"` with error details
- Diff collection writes correct artifacts
- Telemetry includes token counts
- Workspace cleanup runs even on failure

**Estimated effort**: 6h

---

### Phase 4: Prover Upgrades

**Goal**: Evaluate whether Claude Code's output actually satisfies the objective.

#### 4.1 Diff-aware evidence checks

Update `Prover` to recognize `changes.patch` as meaningful evidence:
- Check 1 (existing): Run status = done
- Check 2 (existing): No failure
- **Check 3 (new)**: `changes.patch` is non-empty (for `code_change` operations)
- **Check 4 (new)**: Changed files are within `target_path` scope
- Check 5 (existing): Acceptance criteria → "unverified" (until Phase 5)

#### 4.2 Token/cost evidence

Add evidence item for token usage:
- Record `total_tokens` and `cost_usd` from telemetry
- Flag if cost exceeds a configurable threshold (`JCT_MAX_RUN_COST_USD`)

#### 4.3 Tests

Update `tests/test_prover.py`:
- Empty diff on `code_change` → verdict `fail`
- Non-empty diff within scope → verdict `pass`
- Out-of-scope changes → verdict `partial`
- Cost threshold exceeded → warning in evidence

**Estimated effort**: 3h

---

### Phase 5: LLM-Evaluated Acceptance Criteria (Future)

**Goal**: Use a second Claude call to evaluate whether the diff satisfies the original objective.

This is the v1 upgrade noted in `prover.py` line ~290. Not in scope for initial executor, but the architecture supports it:

- Prover calls `claude -p` with: objective + diff + acceptance criteria
- Claude responds with per-criterion pass/fail and reasoning
- Replaces "unverified" status with actual verdicts

**Deferred until**: Initial executor is validated end-to-end.

---

### Phase 6: Config and CLI Integration

**Goal**: Wire everything together for operator use.

#### 6.1 New config fields

```python
# Claude Code Executor
jct_workspace_root: str          # Workspace cache dir
jct_workspace_cleanup: bool      # Auto-cleanup after run
jct_claude_max_turns: int        # Default max turns (default: 20)
jct_claude_model: str            # Model override (optional)
jct_max_run_cost_usd: float      # Cost ceiling per run (default: 1.00)
```

#### 6.2 CLI update

```bash
# Run with Claude Code executor
python -m devops_control_tower.worker --executor claude_code

# With custom settings
JCT_WORKSPACE_ROOT=/tmp/jct-work \
JCT_CLAUDE_MAX_TURNS=10 \
python -m devops_control_tower.worker --executor claude_code
```

#### 6.3 Documentation

Update `CLAUDE.md` with:
- New executor type and config vars
- Workspace lifecycle explanation
- Cost/token tracking fields

**Estimated effort**: 2h

---

## 4. Implementation Order

| Phase | Task | Effort | Blocks |
|-------|------|--------|--------|
| 1.1 | WorkspaceManager class | 3h | — |
| 1.2 | Workspace tests | 1h | 1.1 |
| 2.1 | PromptBuilder class | 1.5h | — |
| 2.2 | Tool allowlist mapping | 0.5h | 2.1 |
| 2.3 | Prompt tests | 1h | 2.1 |
| 3.1 | ClaudeCodeExecutor class | 3h | 1.1, 2.1 |
| 3.2 | Subprocess + env handling | 1h | 3.1 |
| 3.3 | Result parsing + artifacts | 1.5h | 3.1 |
| 3.4 | Factory registration | 0.5h | 3.1 |
| 3.5 | Executor tests | 2h | 3.1 |
| 4.1 | Diff-aware prover checks | 2h | 3.1 |
| 4.2 | Cost evidence | 0.5h | 3.1 |
| 4.3 | Prover tests | 1h | 4.1 |
| 6.1 | Config fields | 0.5h | 3.1 |
| 6.2 | CLI + docs update | 1h | 6.1 |

**Total estimated effort**: ~20h

---

## 5. New Files

| File | Purpose |
|------|---------|
| `devops_control_tower/worker/workspace.py` | Git workspace lifecycle (clone, worktree, cleanup, diff) |
| `devops_control_tower/worker/prompt.py` | Prompt synthesis from ExecutionContext |
| `devops_control_tower/worker/claude_executor.py` | ClaudeCodeExecutor implementation |
| `tests/test_workspace.py` | Workspace manager tests |
| `tests/test_prompt_builder.py` | Prompt synthesis tests |
| `tests/test_claude_executor.py` | Executor integration tests (mocked subprocess) |

## 6. Modified Files

| File | Change |
|------|--------|
| `devops_control_tower/worker/executor.py` | Add `claude_code` to `get_executor()` factory |
| `devops_control_tower/worker/prover.py` | Diff-aware checks, cost evidence |
| `devops_control_tower/config.py` | New `jct_workspace_*`, `jct_claude_*`, `jct_max_run_cost_usd` fields |
| `devops_control_tower/worker/__main__.py` | Document `--executor claude_code` in help text |
| `CLAUDE.md` | New executor docs, config vars |

---

## 7. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Claude Code CLI interface changes | Executor breaks | Pin to known CLI version; parse defensively |
| API key leaked to subprocess | Security breach | Explicit env sanitization; never inherit full env |
| Runaway token costs | Budget overrun | `jct_max_run_cost_usd` ceiling; kill on threshold |
| Workspace disk exhaustion | Worker crashes | Cleanup on success AND failure; configurable root |
| Claude modifies files outside scope | Unexpected side effects | `--allowedTools` restriction; post-execution scope check in prover |
| Subprocess hangs past timeout | Worker stalls | `subprocess.timeout` with hard kill; worker-level watchdog |

---

## 8. Definition of Done

1. `python -m devops_control_tower.worker --executor claude_code` starts and polls
2. A queued `code_change` task results in Claude Code making real edits
3. `changes.patch` artifact contains the diff
4. Trace folder has full conversation log and token telemetry
5. Prover evaluates the diff (non-empty, in-scope)
6. Review pipeline works unchanged (auto-approve or manual)
7. Workspace cleaned up after run
8. All new tests pass; existing 340 tests unaffected
9. No credentials leak to subprocess beyond `ANTHROPIC_API_KEY`
