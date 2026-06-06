# DECISIONS.md — decision & learnings log

A short running note of the real choices you made: what you tried, what failed and why, what
you changed. This is your engineering judgement on the record — it is what separates a builder
from a button-presser, and it is graded (challenge brief section 08).

Append a 1–2 line entry whenever you make a real decision or hit/fix a wall. Add a timestamp.

Format:
`[HH:MM] <decision or problem> → <what you did and why>`

---

## Example (replace with your own)
- `[10:20]` Chose plain-csv parsing over pandas → fewer deps, fast enough for 5k rows, model
  quota saved for the fixer.
- `[11:05]` Title detector over-counted duplicates → realized non-indexable pages were
  included; added an indexable+200 filter (per rulebook).
- `[12:40]` Dashboard wasn't updating live → MCP tool wasn't emitting the SSE event; added
  `_emit("issue", row)` in extract.

---

## My log
- `[2026-06-06]` Decision: Used pandas for detection instead of iterative CSV parsing to improve performance and allow for vectorised logic.
- `[2026-06-06]` Decision: Implemented graceful failure in fixer.py (returning LLM_FIX_FAILED) instead of crashing the pipeline, ensuring audit completeness despite transient network errors during LLM inference.
- `[2026-06-06]` Decision: Commented out the server.start_dashboard() call in run.py to resolve port-binding conflicts during automated batch testing.
