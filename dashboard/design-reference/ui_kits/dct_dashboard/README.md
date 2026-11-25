# DCT Operator Console — UI kit

The human window into the delivery pipeline. Three screens, fully click-through:

- **Overview** — stat row, streaming runs table (click a row → evidence pack), active agents rail.
- **Review queue** — pending runs as interactive cards; recently decided below.
- **Evidence pack (run detail)** — checks/artifacts/log tabs, evidence summary, approve/reject decision gate with confirmation dialog and toast.

Files: `data.js` (demo data), `Shell.jsx` (sidebar + top bar), `Overview.jsx`, `Queue.jsx`, `RunDetail.jsx`, `App.jsx`, `index.html`.

Composes the design-system primitives from `window.DCTDesignSystem_a2ec41` — nothing re-implemented. Built from the brand brief; no product source existed to recreate, so screens are canonical examples of the described product (agents, runs, evidence packs, human gate).
