# AGENTS.md

Frontend of «Жэка Коммуналкин»: a MAX mini-app on `@maxhub/max-ui` (MAX's UI
kit). pnpm, Node 24. `CLAUDE.md` is a symlink to this file.

## Commands

- `pnpm pre-commit` (lint, format, `tsc -b`) is the gate before every commit;
  nothing runs it for you. Type-checking is `tsc -b`: `tsconfig.json` is a
  solution file, so bare `tsc` checks nothing and exits 0. One file:
  `pnpm eslint <path>`; no per-file type-check. `pnpm test` runs
  `node:test` over `scripts/*.test.ts`; Node strips types but resolves no
  `@/`, so a tested module has only `import type` imports and the test loads
  it by a runtime URL.
- eslint and prettier target `src` only, keeping `.agents/` (vendored docs)
  and top-level configs out. No `.prettierignore`: after `pnpm api` run
  `pnpm format` (openapi-typescript indents 4 spaces).
- `pnpm tunnel` opens a reverse SSH tunnel so MAX can open the local dev
  server (`server.allowedHosts: true` lets its hostname through): copy
  `.env.local.example` to `.env.local`, fill `DEV_TUNNEL_*`; `--help` lists
  flags, `--dry-run` prints the `ssh` command. `DEV_*` vars are read only by
  `scripts/` and `vite.config.ts`: never `VITE_`, never in `shared/env.d.ts`.
- `pnpm mock` runs `mock-config-server` on :31299, a real HTTP backend
  stand-in: requests still go through `openapi-fetch`, react-query and the
  `WebAppData` header (none -> 401 with the real envelope). Entry
  `mock-server.config.ts` is bundled by esbuild (relative imports only, no
  `@/`); handlers live in `src/shared/api/mocks/`, typed with
  `components["schemas"][...]`, and the config is in `tsconfig.app.json`, so a
  mock drifting from the contract fails `tsc -b`. State is in memory.
- The dev server picks the backend: `VITE_API_URL` stays empty (contract paths
  already start with `/api`) and `server.proxy["/api"]` forwards to
  `DEV_API_TARGET`: `http://localhost` (backend behind nginx) or
  `http://localhost:31299` (mock). An absolute mock URL breaks through the
  tunnel, where `localhost` is the phone.

## Architecture: Evolution Design small

`src/` has three layers; imports point down only: `app` -> `features` ->
`shared`. `pnpm lint` enforces folder names and layer direction
(`eslint/folder-structure.ts`, `eslint/independent-modules.ts`); review
enforces the six-unit threshold, "no barrel without a consumer" and "a page
exports `Component`".

### `app/`: composition root

Knows every feature; nothing imports it.

- `router.tsx`: the route tree inside `MaxUI` and `QueryClientProvider`,
  lazy-loading pages by deep path (`@/features/home/home.page`), the one
  allowed deep import, since `lazy()` needs a module exporting `Component`
  and each page keeps its own chunk.
- Chrome lives in layout routes, never in pages: one renders `TabBar` under
  root tabs; `PushedPage` turns on the MAX header back button for screens
  pushed over a root (`fallback` is where back goes without history). There
  is no in-app back bar: the app opens only inside MAX, whose header always
  has the back arrow. A screen never wires back itself: place it under the
  right layout.
- `protected-loader.ts`: `protectedLoader` on the pathless route wrapping
  every in-app screen redirects to `Routes.OUTSIDE_MAX` when `isInsideMax` is
  false; the stub route sits outside it. `session-loader.ts` and
  `deeplink-loader.ts` route a launch to its start screen or run a deeplink.
- `app.tsx` renders `ScrollRestoration`: a pushed screen opens at the top and
  back restores the old position, so a page never scrolls itself on mount.
- `app.tsx` alone imports `globals.css`, the only global stylesheet: max-ui
  styles, `color-scheme: light dark` on `:root`, and two resets
  (`-webkit-tap-highlight-color: transparent`; `:where(:focus) { outline:
  none }`, zero specificity so deliberate `:focus-visible` outlines win).
  `color-scheme` is load-bearing: without it Android WebView force-darkens
  and inverts the app in MAX's dark theme (`index.html` repeats it as a
  `<meta>` for the first paint). Inverted colours on a phone: check it before
  touching any token. It holds only these; a rule that paints something goes
  in that thing's module, palette overrides nowhere.

### `features/<feature>/`

- A feature is a piece of product value a non-developer could name
  (`onboarding`, `home`), never a technical bucket or an FSD slice. It owns its
  pages, components, state and styles.
- Outsiders import only its `index.ts` barrel. No external consumer, no
  barrel: re-exporting a page would pull it out of its lazy chunk.
- Flat while it holds at most 6 units (a component plus its `.module.css` is
  one unit). Past six, contents move into these groups only: `ui/`
  (components, styles), `model/` (state, react-query hooks), `domain/` (pure
  rules and types: no React, I/O or network), `lib/` (feature-only helpers),
  `api/` (its requests). The threshold is per folder; a one-unit group is
  noise.
- `<name>.page.tsx` and its CSS stay in the feature root even when grouped.
- An outgrown feature splits into nested sub-features, each with its own
  `index.ts`, same rules.
- Inside a feature: `ui` -> `model` -> `domain`; `lib` serves all.
- A sibling feature is imported only through its barrel, and rarely. Code for
  one feature lives in it; a second user imports the barrel or duplicates;
  a third, product-agnostic, moves it to `shared`; product-specific shared
  code is a `services` layer candidate: discuss first.

### `shared/`: last resort, product-agnostic

- `api/`: `instance.ts` (`fetchClient` from `openapi-fetch`, wrapped as
  `rqClient` by `openapi-react-query`), `query-client.ts` (`QueryClient`,
  `invalidatePaths`), `errors.ts` (`errorDetail`, `isForbidden`,
  `isConflict`, `isUnauthorized`, `retryUnlessForbidden`; `errorMessage(error,
  fallback)` is what users see: the server reason for a 4xx, the
  session-expired text for a 401, the fallback for network and 5xx),
  `next-offset.ts` (offset `getNextPageParam`). `schema/generated.ts` comes
  from `pnpm api` against the running backend; never edit it by hand; it is
  committed because the Docker build has no backend.
- `model/routes.ts` is the only source of paths (`Routes.HOME`); never
  hardcode one. `model/session.ts` holds `/me` and what is shown: cabinet
  (resident or admin), residency, organization, in one `localStorage` value
  parsed with zod on every read (anything not admin reads as resident, a bad
  id as absent), so `houseParams()`, `orgParams()` (outside React) and screens
  agree. Switching residency or organization invalidates the whole query
  cache (they change a request header); switching the cabinet does not.
  `startTarget(session)` is the one rule for where a launch lands, a semantic
  target (`admin`, `home`, `onboarding`) the caller maps to a route.
- `lib/`: `css.ts` (`cn`), `format.ts` (dates, numbers, `plural`),
  `router.ts` (`useRouteParams`, zod-parsed), `analytics/` (`useTrack` ->
  `/api/events`), `max/` (the Bridge: typed `getWebApp`, `getMaxLaunch` with
  `isInsideMax`, `initData`, `startParam`, `useBackNavigation`,
  `useClosingConfirmation(active)` for forms with unsaved input,
  `haptic.success/error/select`, and `scanCode()` over `openCodeReader`
  with the gallery allowed: `null` on cancel or without the method; the
  bridge defines the method on every platform, so `canScanCode()` shows a
  scan button only on iOS and Android). The bridge is the
  CDN script in `index.html`; outside MAX `getWebApp()` is `null` and the
  back button, closing confirmation and haptics are no-ops (the web and
  desktop clients have no haptics either).
- `ui/`: the kit over max-ui. A date field is `DateInput` (mask ДД.ММ.ГГГГ,
  value an ISO day or `""` until the date is full and real), never a native
  `type="date"`: the MAX WebView draws an empty one as a blank box. A choice
  from a list is a cell that opens `BottomSheet` with radio cells, never a
  native `<select>`: MAX draws its own system dialog for it. Every recharts chart goes in `ChartBox` (owns
  `ResponsiveContainer`, kills the tap focus ring from `accessibilityLayer`),
  never a bare `<div>`; axis labels are styled with the axis `tick` prop,
  since recharts 3 draws them outside the axis group and a `className` on the
  axis never reaches them. `StatusPill` is the one status badge of both
  cabinets; its `tone` is a subset of `IconTileTone`, so one tone map feeds a
  row's tile and badge; never re-create or restyle it in a screen's CSS.
- `env.d.ts` declares every `VITE_*` var.
- No assets folder: static files sit next to their component; icon SVGs live
  in `shared/ui/icon/`, exported with `Icon` from its barrel
  (`import { Icon, navHomeIcon } from "@/shared/ui/icon"`).

## Conventions

- Files and folders are kebab-case; a page ends with
  `export const Component = <Name>Page`.
- CSS Modules only, colocated `<name>.module.css`, camelCase locals; block
  classes PascalCase (`styles.TabBar`), variant classes lowercase
  (`styles[tone]`).
- The app runs only on a phone inside MAX: design for 320-400px and check at
  360 and 393. Two buttons rarely fit in a row (content width, let them wrap);
  the kit truncates long labels with an ellipsis silently.
- A name is earned by a second use: single-use strings, numbers, objects and
  copy go inline (a review rule).
- `@/*` is `src/*`: relative imports inside a module, `@/` across modules.
- Untrusted input (Bridge, URL, storage) is parsed with zod at the boundary
  and typed via `z.infer`; our API is typed by the generated schema. reactuse
  storage hooks return unchecked `JSON.parse` output: validate at the call
  site.
- UI uses max-ui primitives (`Button`, `Container`, `Flex`, `Panel`,
  `Typography`) before hand-rolled ones.
- Generic hooks come from `@siberiacancode/reactuse` (package-root import,
  any layer, never wrapped in `shared`); check `.agents/skills/reactuse/`
  before writing a hook, and add one to `shared/lib` only when it has none.
- Forms: `react-hook-form` + a zod schema via `zodResolver`, never `useState`
  chains or reactuse's `useForm` (DOM-held values, no `useFieldArray`). Field
  limits are `formConstraints` in the feature's `domain/`, shared by the
  schema and `maxLength`; every text field has one, long text uses the kit's
  `Textarea`, and a submit button is never `position: sticky` (the mobile
  keyboard renders it translucent).
