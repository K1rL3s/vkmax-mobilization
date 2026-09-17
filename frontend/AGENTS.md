# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Frontend for "Жека Коммуналкин" — a mini-app for the MAX messenger (built with `@maxhub/max-ui`, MAX's own UI kit) covering utility-company requests, meter readings, and resident polls for apartment buildings. Package manager is `pnpm`; Node 24.

## Commands

```
pnpm dev              # vite dev server
pnpm build             # tsc -b && vite build (type-check, then build)
pnpm lint              # eslint .
pnpm format            # prettier --write .
pnpm preview           # preview a production build
pnpm api               # regenerate src/shared/api/schema/generated.ts from schema/main.yaml
```

There is no test runner configured in this package.

To run a single lint check on one file: `pnpm eslint <path>`. There's no equivalent narrowing for `tsc -b` (project-reference build); run `pnpm build` for full type-checking.

## Architecture

Feature-Sliced Design-style layout under `src/`:

- `src/app/` — composition root. `main.tsx` mounts `Router`; `router.tsx` builds the `react-router-dom` v7 router and wires routes to lazily-imported page modules (lazy route modules export a `Component`, e.g. `onboarding.page.tsx` exports `export const Component = OnboardingPage`). `providers.tsx` wraps the tree in `MaxUI` (from `@maxhub/max-ui`) and `QueryClientProvider`. `app.tsx` is the router-level layout (`<Outlet />`).
- `src/features/<feature>/` — one directory per feature (currently `onboarding`), each with an `index.ts` barrel and a `<feature>-page/` holding the page component + CSS module.
- `src/shared/` — cross-feature code:
  - `shared/model/routes.ts` — the single source of truth for route paths (`Routes.ONBOARDING`, etc.) — reference this instead of hardcoding path strings.
  - `shared/model/config.ts` — reads build-time env into `CONFIG` (currently just `CONFIG.API_URL` from `import.meta.env.VITE_API_URL`).
  - `shared/api/instance.ts` — the typed API client: `openapi-fetch` (`fetchClient`) wrapped by `openapi-react-query` (`rqClient`), typed from `ApiPaths`.
  - `shared/api/schema/main.yaml` — the OpenAPI spec (hand-maintained). `shared/api/schema/generated.ts` is generated from it via `pnpm api` — never edit `generated.ts` by hand, and regenerate it after changing `main.yaml` or after the backend's API changes.
  - `shared/env.d.ts` — declares the `ImportMetaEnv` shape; add new `VITE_*` vars here when adding them to `config.ts`.

New features should follow the same shape: a directory under `src/features/`, a barrel `index.ts`, and page/component files colocated with their `.module.css`.

**Layering rule (dependencies only point downward):** `app` → `features` → `shared`. A lower layer must never import from a layer above it — `shared` cannot reach into `features` or `app`, and one feature cannot reach into another feature's internals. `shared` changes rarely and is depended on everywhere, so it must stay stable and feature-agnostic. `features` change constantly (per-feature work), so nothing else should build a hard dependency on a specific feature's internals — if a feature needs something from a sibling feature, import only that sibling's public API (its `index.ts` barrel), never its internal files.

## Conventions

- CSS Modules only, with `camelCase` locals and scoped class names (see `vite.config.ts`); no global stylesheets beyond what `@maxhub/max-ui` ships.
- Path alias `@/*` → `src/*` (configured in both `tsconfig.json` and `vite.config.ts`).
- UI components come from `@maxhub/max-ui` (MAX's design system) — prefer its primitives (`Button`, `Container`, `Flex`, `Panel`, `Typography`, ...) over hand-rolled ones.
