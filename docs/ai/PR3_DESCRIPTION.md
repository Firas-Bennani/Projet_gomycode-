# Industrial_Copilot — rename, authentication, richer seed data, Events and Clients pages

Final pass before submission, branch `final-touches` off `upstream/main`. Items were done in a
fixed order with a commit after each, and the three demo scenarios were kept working throughout.

## 1. Rename to `Industrial_Copilot`

The product name is exactly **`Industrial_Copilot`**. Updated everywhere it is user-visible —
browser tab title, dashboard header, backend `PROJECT_NAME` and startup logs, README title and
prose, and our own docs. **No code identifiers or file names were renamed**, so nothing imports
differently and no teammate's import breaks.

The separate `standalone-3d-ai-copilot/` app was left alone: it is a teammate's parallel build with
its own branding, and renaming inside it was not asked for.
