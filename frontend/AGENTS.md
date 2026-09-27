# AGENTS.md

The working agreement for this repository — for coding agents and for people. `CLAUDE.md` is a symlink to this file.

## Project

Frontend for "Жека Коммуналкин" — a mini-app for the MAX messenger (built with `@maxhub/max-ui`, MAX's own UI kit) covering utility-company requests, meter readings, and resident polls for apartment buildings. Package manager is `pnpm`; Node 24.

## Commands

```
pnpm dev              # vite dev server
pnpm build             # tsc -b && vite build (type-check, then build)
pnpm lint              # eslint ./src
pnpm format            # prettier --write ./src
pnpm preview           # preview a production build
pnpm pre-commit        # lint, format, type-check — run before every commit
pnpm api               # regenerate src/shared/api/schema/generated.ts from the running backend
pnpm tunnel            # reverse SSH tunnel: expose the local dev server on the test host
pnpm mock              # mock-config-server on :31299, the stand-in backend
```

There is no test runner configured in this package.

`pnpm pre-commit` is the gate to run before committing: `eslint ./src`, then `prettier --write ./src`, then `tsc -b`. Despite the name, nothing runs it automatically — no hook manager is installed, so it is a command you type. Two things to know about it: the type-check must stay `tsc -b`, because `tsconfig.json` is a solution file (`"files": []` plus project references) and a bare `tsc` silently checks nothing and exits 0; and both `eslint` and `prettier` are pointed at `src` rather than the repository root, so the vendored docs under `.agents/` and the config files at the top level stay out of the diff. There is no `.prettierignore`: the generated `schema/generated.ts` is formatted like every other file, which is why `format` runs after codegen — `openapi-typescript` indents with four spaces and prettier rewrites that to two.

`scripts/tunnel.ts` (run via `pnpm tunnel`, executed directly by Node's TypeScript stripping) opens a reverse SSH tunnel forwarding the local dev server to a port on the remote host, so the mini-app can be opened from MAX for testing. Copy `.env.local.example` to `.env.local` (gitignored via `*.local`) and fill in the `DEV_TUNNEL_*` values before the first run — nothing host-specific is hardcoded. Precedence for every setting is CLI flag → environment (shell wins over `.env.local`, which wins over `.env`) → default; `--dry-run` prints the resulting `ssh` command, `pnpm tunnel --help` lists each flag with its variable. These `DEV_*` variables are read only by the script (no `VITE_` prefix), never reach the client bundle, and must not be added to `shared/env.d.ts`. `DEV_API_TARGET` follows the same rule but is read by `vite.config.ts` instead — see the mock server below. The dev server accepts any Host header (`server.allowedHosts: true` in `vite.config.ts`), so the tunnelled public hostname works without further configuration.

To run a single lint check on one file: `pnpm eslint <path>`. There's no equivalent narrowing for `tsc -b` (project-reference build); run `pnpm build` for full type-checking.

### Mock server

`pnpm mock` starts [`mock-config-server`](https://github.com/siberiacancode/mock-config-server) on port 31299 — a real HTTP server standing in for the backend, not a layer of fake data inside the app. Requests keep going through `openapi-fetch`, react-query and the `WebAppData` header exactly as they will against the real backend, which is the point: switching over must not surface any difference.

`mock-server.config.ts` at the package root is the entry point (esbuild bundles it, so plain relative imports work but the `@/` alias does not); the handlers live in `src/shared/api/mocks/`. Every response is typed with `components["schemas"][...]` from the generated contract, and the config file is inside `tsconfig.app.json`'s `include`, so a mock that drifts from the contract fails `tsc -b`. The mock holds its state in memory: accepting the consent changes what `/me` returns, linking a house adds a residency. A request without the `WebAppData` header gets a 401 with the real error envelope.

Which backend the app talks to is decided by the dev server, not the client: `VITE_API_URL` stays empty (the contract's own paths already start with `/api`, so a `/api` prefix here would produce `/api/api/...`) and `server.proxy["/api"]` forwards to `DEV_API_TARGET` — `http://localhost` for the real backend behind nginx, `http://localhost:31299` for the mock. An absolute mock URL would not work through `pnpm tunnel`, where the mini-app runs on a phone and `localhost` is the phone itself.

## Architecture

The project follows **Evolution Design, ED small** (https://github.com/evo-community/evolution-design). Its central idea: a folder is an architectural boundary, not a pile of files. Three layers live under `src/`:

```
src/
  app/        composition root — knows every feature
  features/   business features — everything the product is made of
  shared/     infrastructure — the last resort
```

### `src/app/` — composition root

The only place that knows about every feature. **Nothing may import from `app`.**

- `main.tsx` - mounts `Router`.
- `router.tsx` - the `react-router-dom` v7 route tree, wrapped in `MaxUI` (`@maxhub/max-ui`) and `QueryClientProvider`; wires paths from `shared/model/routes.ts` to lazily-imported page modules. Cross-cutting chrome lives in layout routes, not in pages: one renders the `TabBar` under the root tab screens, and `PushedPage` turns on the MAX header back button for everything opened on top of a root (its `fallback` is where back goes when the screen was opened with no history behind it). A screen never wires the back button itself - it is placed under the right layout instead.
- `protected-loader.ts` - the access rule. `protectedLoader` sits on the pathless route that wraps every in-app screen and redirects to `Routes.OUTSIDE_MAX` when the app was not opened from MAX (`isInsideMax`); the stub route sits outside it.
- `session-loader.ts` and `deeplink-loader.ts` - the route loaders that read the session and send a launch to its start screen or run a deeplink.
- `app.tsx` — the root layout (`<Outlet />`), and the one place that pulls in `globals.css`.
- `globals.css` — the only global stylesheet, and it stays tiny: it `@import`s `@maxhub/max-ui/dist/styles.css`, declares `color-scheme: light dark` on `:root`, and resets two platform annoyances — `-webkit-tap-highlight-color: transparent` (inherited, so one declaration covers everything) and `:where(:focus) { outline: none }`, which kills the ring the webview leaves on every tapped control while `:where()`'s zero specificity lets the deliberate `:focus-visible` outlines in `checkbox`, `faq`, `request-choice` and the admin request row still win. **The `color-scheme` line is load-bearing.** Without it Android WebView treats the mini-app as a page that does not understand dark mode and applies its own algorithmic darkening ("force dark"), inverting whatever we paint: in MAX's dark theme white icons and text came out black, greys came out muddy, and a whole layer of hand-picked opaque token overrides used to live in this file trying to compensate. Declaring the schemes hands the theme back to the kit, so both palettes render as authored. `index.html` carries the same declaration as `<meta name="color-scheme" content="light dark">`, which applies before the first paint. If colours ever look inverted on a phone again, check that declaration before touching a single token.

### `src/features/<feature>/` — business features

A feature is **a piece of product value**, named the way the product is discussed: `onboarding`, `home`, `tab-bar`. It is not a technical bucket (`components`, `hooks`, `utils`) and not an FSD-style use-case slice. The test: could a non-developer name it?

Every feature owns everything it needs - pages, components, state, styles. When something outside needs the feature, it gets an `index.ts` barrel and is imported as `@/features/<feature>`, never by a deep path. A feature with no external consumer has no barrel: an empty `index.ts` is worse than none, and re-exporting a page from one would pull it out of its lazy chunk.

A feature grows through ED's evolution stages, and no further than it currently needs:

**Flat while it fits.** A feature is a flat folder — files side by side, no subfolders — until it holds **more than 6 units**. Up to six, flat is the correct shape; don't create folders "for later".

A unit is one thing you can name, not one file on disk: a component and its colocated `.module.css` count as **one** unit, as does a page with its stylesheet. Otherwise CSS Modules would halve the threshold and force grouping at three components.

**Grouped past six.** When a folder outgrows six units, its contents move into the agreed groups — and only these:

| group     | what belongs in it                                           |
| --------- | ------------------------------------------------------------ |
| `ui/`     | components, presentation, styles                             |
| `model/`  | state and data flow: stores, react-query hooks               |
| `domain/` | pure business rules and types — no React, no I/O, no network |
| `lib/`    | technical helpers used only inside this feature              |
| `api/`    | this feature's requests and contracts                        |

A group only organizes files; a module is an abstraction with a public API. A group holding one unit is noise — the threshold applies to each folder on its own, so a feature can be grouped while a sibling stays flat.

**Pages are the exception.** `<name>.page.tsx` and its CSS module stay in the feature root even after the feature is grouped. A page is the feature's entry point, it is what the router deep-imports, and `react-router` dictates its shape (`export const Component`), so it does not move into `ui/`.

**Sub-features.** A feature that outgrew its groups splits into nested features underneath itself, each with its own `index.ts`, recursively following the same rules. The parent composes them and re-exports what the outside world needs.

### `src/shared/` — infrastructure

`shared` is the **last resort**: code lands here only when it is genuinely feature-agnostic and needed in more than one place. It uses the same group vocabulary as a feature:

- `shared/api/` - `instance.ts` is the typed API client (`openapi-fetch` as `fetchClient`, wrapped by `openapi-react-query` as `rqClient`); `query-client.ts` holds the `QueryClient` and `invalidatePaths`; `errors.ts` reads the API error envelope (`errorDetail`, `isForbidden`, `isConflict`, `retryUnlessForbidden`); `next-offset.ts` is the `getNextPageParam` of offset pagination. `schema/generated.ts` is written by `pnpm api`, which points `openapi-typescript` straight at the running backend (`http://localhost/api/openapi.json`) - the tool fetches the URL itself, so no copy of the spec is kept in the repository and the backend has to be up to regenerate. Never edit the file by hand. It is committed even though it is generated, because the Docker build runs `pnpm build` with no backend in reach; `.gitattributes` marks it `linguist-generated` so review collapses it.
- `shared/model/` - `routes.ts` is the single source of truth for route paths (`Routes.HOME`, …); never hardcode a path string. `session.ts` holds `/me` plus what the app is currently showing: which cabinet (resident or utility-company), which residency, and which organization. The three live in one `localStorage` value, parsed with `zod` on every read - anything that is not the admin cabinet reads as the resident one, a bad id reads as absent - so `houseParams()` and `orgParams()`, which run outside React, and the screens all see the same choice. Switching the residency or the organization invalidates the whole query cache, because both change a request header; switching the cabinet does not. `startTarget(session)` is the one rule for where a launch lands - the semantic target (`admin`, `home`, `onboarding`), never a route: the caller maps it, so the session model knows nothing about routing.
- `shared/lib/` - technical utilities: `css.ts` (`cn`), `format.ts` (dates, numbers, `plural`), `router.ts` (`useRouteParams`, route params parsed with `zod`), `analytics/` (`useTrack`, product events posted to `/api/events`) and `max/`, the MAX Bridge module - a typed `window.WebApp` (`getWebApp`), launch data (`getMaxLaunch`: `isInsideMax`, `initData` for the auth header, `startParam`), and the header back button (`useBackNavigation`). The bridge itself is the CDN script loaded in `index.html`; outside MAX `getWebApp()` is `null`, the launch reads as not inside MAX and the back button is a no-op.
- `shared/ui/` — the kit on top of `@maxhub/max-ui`: `autocomplete/`, `card/`, `chart-box/`, `checkbox/`, `chevron/`, `confirm-dialog/`, `field-error/`, `icon/`, `icon-tile/`, `state/`, `status-pill/`. `ChartBox` is the frame every `recharts` chart goes in - it owns the `ResponsiveContainer` and kills the focus ring the chart `<svg>` draws on a tap in the mini-app (`accessibilityLayer` puts `tabindex` on it), so a chart is never dropped into a bare `<div>`. `StatusPill` is the one status badge of both cabinets — a rounded label whose `tone` (`themed`, `promo`, `neutral`, `positive`, `negative`) is a subset of `IconTileTone`, so one tone map feeds a row's tile and its badge. A screen never re-rolls that pill in its own CSS module.
- `shared/env.d.ts` - declares `ImportMetaEnv`; add every new `VITE_*` var here.

There is no `assets` segment, by design: static files live next to the component that uses them. The icon SVGs sit in `shared/ui/icon/` and are exported from its barrel together with `Icon`, so a consumer writes a single import:

```ts
import { Icon, navHomeIcon } from "@/shared/ui/icon";
```

### Dependency rules

Dependencies point **downward only: `app` → `features` → `shared`.**

- Nothing imports from `app`.
- `shared` never reaches into `features` or `app`. It changes rarely and is depended on everywhere, so it must stay stable and product-agnostic.
- Feature → sibling feature is allowed in ED small, but only through the sibling's `index.ts`, never its internals — and keep it rare. Every such import is a signal; by the third one the code probably belongs in `shared` (or in a `services` layer worth introducing).
- Inside a feature the same direction holds: `ui` → `model` → `domain`. `domain` is the bottom — pure, testable, importing nothing from above it. `lib` is available to everything in the feature.

**One documented exception.** `router.tsx` imports page modules by deep path (`@/features/home/home.page`) instead of through a barrel, because react-router's `lazy()` requires a module that exports `Component` and each page must stay in its own chunk. Routing is the composition root's job, so this stays as it is — everything else goes through barrels.

### Where does this code go?

1. Used by one feature → inside that feature.
2. Used by a second feature → import that feature's barrel, or duplicate. Don't generalize on the second use.
3. Used by a third, and free of product specifics → `shared`.
4. Product-specific but genuinely shared → a candidate for a `services` layer; discuss before adding one.

### Enforcement

Most of the rules above are checked by `pnpm lint` — `eslint-plugin-project-structure`, wired up in `eslint.config.js` with two config files:

- `eslint/folder-structure.ts` (`project-structure/folder-structure`) — which folders and filenames may exist under `src/`. Groups are restricted to `ui|model|domain|lib|api`, names are kebab-case, files must be one of `index.ts`, `*.page.tsx`, `*.mock.ts`, `*.tsx`, `*.ts`, `*.module.css`, `*.svg`, `*.yaml` — plus `globals.css`, allowed in `app` alone, which is what keeps a second global stylesheet from appearing. Any nested sub-feature or module folder must contain an `index.ts`, which is what stops `helpers/`-style junk folders from appearing. It lints CSS, SVG and YAML too, not just TypeScript.
- `eslint/independent-modules.ts` (`project-structure/independent-modules`) — the layer direction. `shared` may import only `shared`; a feature may import `shared`, its own subtree (via the `{family_3}` reference, so no config change is needed when a feature is added), and a sibling feature's top-level `index.ts`; `app` may import feature barrels plus `*.page.tsx` for the `lazy()` exception.

Three rules are deliberately **not** automated, because they need a view of a whole folder or file rather than one import: the six-unit flat threshold, "no barrel without a consumer", and "`*.page.tsx` exports `Component`". Watch for those in review.

## Conventions

- Files and folders are `kebab-case`. Pages are `<name>.page.tsx` and end with `export const Component = <Name>Page` so the router can lazy-load them.
- A module that is imported from outside has an `index.ts` barrel — that barrel is its public API and the only thing outsiders may import. No consumer, no barrel.
- CSS Modules only, colocated as `<name>.module.css` (`camelCase` locals, scoped names — see `vite.config.ts`). Block classes are `PascalCase` (`styles.TabBar`); variant classes are lowercase so they can be looked up dynamically (`styles[tone]`). The single global stylesheet is `app/globals.css`, and it holds only the `color-scheme` declaration and two platform resets — see `src/app/` above; a rule that paints something belongs in that something's module, and palette overrides belong nowhere.
- The app only ever runs on a phone, inside MAX: the target viewport is **320-400px wide**, and every screen is checked there. Nothing is designed for a desktop width — a layout that only works wider is broken, not "fine on big screens". Two practical consequences: a row of two buttons rarely fits (give them content width and let them wrap), and a label that fits at 560px says nothing about 393px, where the kit silently truncates it with an ellipsis. Check at 360 and 393 before calling a screen done.
- A constant earns its name by being used more than once. A string, number or
  object referenced in exactly one place goes inline at that place: hoisting it
  to the top of the file only makes the reader jump. This holds for user-facing
  copy too — when those strings eventually move, they move into translations,
  not into a block of `SCREAMING_CASE` at the top of a page. No lint rule
  covers this (nothing in eslint or the installed plugins counts references
  like that), so it is a review rule.
- Path alias `@/*` → `src/*` (configured in both `tsconfig.json` and `vite.config.ts`). Within a module import relatively; across modules use `@/`.
- Untrusted input — anything coming from the MAX Bridge, a URL, or storage — is parsed with `zod` at the boundary it enters, and the app-facing type is inferred from the schema (`z.infer`) so the shape and its validation cannot drift apart. Our own API is the exception: it is typed by the generated OpenAPI schema.
- UI comes from `@maxhub/max-ui` (MAX's design system) — prefer its primitives (`Button`, `Container`, `Flex`, `Panel`, `Typography`, …) over hand-rolled ones.
- Generic React hooks come from [`@siberiacancode/reactuse`](https://siberiacancode.github.io/reactuse/) — the same rule as the UI kit: reach for the library before hand-rolling, and add a hook to `shared/lib` only when the library has no equivalent. It is infrastructure like `react` itself, so every layer may import it directly (`independent-modules` constrains our own folders, not external packages) and it is never wrapped in a `shared` barrel. Import from the package root: `import { useDebounceValue } from "@siberiacancode/reactuse"`. The vendored reference lives in `.agents/skills/reactuse/` — check the hook list there before writing a hook by hand.
- Forms are built with [`react-hook-form`](https://react-hook-form.com) and a `zod` schema through `zodResolver` from `@hookform/resolvers/zod` — not with hand-rolled `useState` and `if` chains, and not with `useForm` from `reactuse` (its values live in DOM nodes, so an array field cannot live there and `useFieldArray` has no equivalent). Field limits are a business rule and live in the feature's `domain/` as `formConstraints`, so the schema and the `maxLength` on the field read the same number. Every text field carries a limit, long text uses `Textarea` from the kit, and the submit button is never `position: sticky` — the mobile keyboard renders a stuck button translucent.
- One exception to that rule: storage hooks (`useLocalStorage`, `useSessionStorage`, `useCookie`) return whatever `JSON.parse` produced, typed by the generic you passed rather than by anything checked at runtime. That is precisely the untrusted input the `zod` rule above covers, so validate the value at the call site instead of trusting the type parameter.
