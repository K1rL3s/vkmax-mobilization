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

- `main.tsx` — mounts `Router`.
- `router.tsx` — the `react-router-dom` v7 route tree; wires paths from `shared/model/routes.ts` to lazily-imported page modules. Cross-cutting chrome lives in layout routes, not in pages: one renders the `TabBar` under the root tab screens, and `PushedScreen` turns on the MAX header back button for everything opened on top of a root (its `fallback` is where back goes when the screen was opened with no history behind it). A screen never wires the back button itself — it is placed under the right layout instead.
- `protected-loader.ts` — the access rule. `protectedLoader` sits on the pathless route that wraps every in-app screen and redirects to `Routes.OUTSIDE_MAX` when the app was not opened from MAX (`isInsideMax`); `outsideMaxLoader` bounces the other way, so a MAX user can never get stuck on the stub. It is deliberately inert in dev builds (`import.meta.env.DEV`) — otherwise `pnpm dev` in a browser would redirect on every route and local work would be impossible.
- `providers.tsx` — wraps the tree in `MaxUI` (`@maxhub/max-ui`) and `QueryClientProvider`.
- `app.tsx` — the root layout (`<Outlet />`).

### `src/features/<feature>/` — business features

A feature is **a piece of product value**, named the way the product is discussed: `onboarding`, `home`, `tab-bar`. It is not a technical bucket (`components`, `hooks`, `utils`) and not an FSD-style use-case slice. The test: could a non-developer name it?

Every feature owns everything it needs — pages, components, state, mocks, styles. When something outside needs the feature, it gets an `index.ts` barrel and is imported as `@/features/<feature>`, never by a deep path. A feature with no external consumer has no barrel: an empty `index.ts` is worse than none, and re-exporting a page from one would pull it out of its lazy chunk.

A feature grows through ED's evolution stages, and no further than it currently needs:

**Flat while it fits.** A feature is a flat folder — files side by side, no subfolders — until it holds **more than 6 units**. Up to six, flat is the correct shape; don't create folders "for later".

A unit is one thing you can name, not one file on disk: a component and its colocated `.module.css` count as **one** unit, as does a page with its stylesheet. Otherwise CSS Modules would halve the threshold and force grouping at three components.

**Grouped past six.** When a folder outgrows six units, its contents move into the agreed groups — and only these:

| group     | what belongs in it                                           |
| --------- | ------------------------------------------------------------ |
| `ui/`     | components, presentation, styles                             |
| `model/`  | state and data flow: stores, react-query hooks, mocks        |
| `domain/` | pure business rules and types — no React, no I/O, no network |
| `lib/`    | technical helpers used only inside this feature              |
| `api/`    | this feature's requests and contracts                        |

A group only organizes files; a module is an abstraction with a public API. A group holding one unit is noise — the threshold applies to each folder on its own, so a feature can be grouped while a sibling stays flat.

**Pages are the exception.** `<name>.page.tsx` and its CSS module stay in the feature root even after the feature is grouped. A page is the feature's entry point, it is what the router deep-imports, and `react-router` dictates its shape (`export const Component`), so it does not move into `ui/`.

**Sub-features.** A feature that outgrew its groups splits into nested features underneath itself, each with its own `index.ts`, recursively following the same rules. The parent composes them and re-exports what the outside world needs.

Where the features stand today — all three flat, well inside the threshold:

```
features/
  home/          home.page.tsx + css, demand-card.tsx, home.mock.ts   3 units
  onboarding/    three pages + css in the root, hooks and types
                 grouped in model/                        3 + 6 units
  error/         error.page.tsx + css                                  1 unit
  tab-bar/       tab-bar.tsx + css, index.ts                          2 units
  outside-max/   outside-max.page.tsx + css                            1 unit
```

`onboarding/model/` is the first place the grouping rule bit: the feature holds a
page per screen plus a hook per job — house search, flat search, linking, the
view model composing them, and the consent hook — which is past six units in one
folder.

### `src/shared/` — infrastructure

`shared` is the **last resort**: code lands here only when it is genuinely feature-agnostic and needed in more than one place. It uses the same group vocabulary as a feature:

- `shared/api/` — `instance.ts` is the typed API client (`openapi-fetch` as `fetchClient`, wrapped by `openapi-react-query` as `rqClient`); `query-client.ts` holds the `QueryClient`. `schema/generated.ts` is written by `pnpm api`, which points `openapi-typescript` straight at the running backend (`http://localhost/api/openapi.json`) — the tool fetches the URL itself, so no copy of the spec is kept in the repository and the backend has to be up to regenerate. Never edit the file by hand. It is committed even though it is generated, because the Docker build runs `pnpm build` with no backend in reach; `.gitattributes` marks it `linguist-generated` so review collapses it.
- `shared/model/` — `routes.ts` is the single source of truth for route paths (`Routes.HOME`, …); never hardcode a path string. `config.ts` reads build-time env into `CONFIG`. `session.ts` holds `/me` plus the address the cabinet is shown for: a resident of several houses picks one on `/residencies`, the choice is kept in `localStorage` (validated with `zod` on read, like any other storage value) and published through `useSyncExternalStore`, so `houseParams()` — which runs outside React — and the screens see the same address. Switching invalidates the whole query cache: every loaded request, meter and house card belongs to the address left behind.
- `shared/lib/` — technical utilities: `css.ts` (`cn`) and `max/`, the MAX Bridge module — a typed `window.WebApp`, launch data (`useMaxLaunch`, `useMaxUser`, and `getInitData` for the auth header), and the header back button (`useBackButton`, `useBackNavigation`). The bridge itself is the CDN script loaded in `index.html`; outside MAX every value degrades to `null` and the back button is a no-op, so the app stays runnable in a plain browser.
- `shared/ui/` — the kit on top of `@maxhub/max-ui`: `card/`, `icon/`, `icon-tile/`.
- `shared/env.d.ts` — declares `ImportMetaEnv`; add every new `VITE_*` var here alongside `config.ts`.

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

- `eslint/folder-structure.ts` (`project-structure/folder-structure`) — which folders and filenames may exist under `src/`. Groups are restricted to `ui|model|domain|lib|api`, names are kebab-case, files must be one of `index.ts`, `*.page.tsx`, `*.mock.ts`, `*.tsx`, `*.ts`, `*.module.css`, `*.svg`, `*.yaml`. Any nested sub-feature or module folder must contain an `index.ts`, which is what stops `helpers/`-style junk folders from appearing. It lints CSS, SVG and YAML too, not just TypeScript.
- `eslint/independent-modules.ts` (`project-structure/independent-modules`) — the layer direction. `shared` may import only `shared`; a feature may import `shared`, its own subtree (via the `{family_3}` reference, so no config change is needed when a feature is added), and a sibling feature's top-level `index.ts`; `app` may import feature barrels plus `*.page.tsx` for the `lazy()` exception.

Three rules are deliberately **not** automated, because they need a view of a whole folder or file rather than one import: the six-unit flat threshold, "no barrel without a consumer", and "`*.page.tsx` exports `Component`". Watch for those in review.

## Conventions

- Files and folders are `kebab-case`. Pages are `<name>.page.tsx` and end with `export const Component = <Name>Page` so the router can lazy-load them. Mocks are `<name>.mock.ts` inside `model/`.
- A module that is imported from outside has an `index.ts` barrel — that barrel is its public API and the only thing outsiders may import. No consumer, no barrel.
- CSS Modules only, colocated as `<name>.module.css` (`camelCase` locals, scoped names — see `vite.config.ts`). Block classes are `PascalCase` (`styles.TabBar`); variant classes are lowercase so they can be looked up dynamically (`styles[tone]`). No global stylesheets beyond what `@maxhub/max-ui` ships.
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
- One exception to that rule: storage hooks (`useLocalStorage`, `useSessionStorage`, `useCookie`) return whatever `JSON.parse` produced, typed by the generic you passed rather than by anything checked at runtime. That is precisely the untrusted input the `zod` rule above covers, so validate the value at the call site instead of trusting the type parameter.
