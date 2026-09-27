import { createIndependentModules } from "eslint-plugin-project-structure";

export const independentModulesConfig = createIndependentModules({
  modules: [
    {
      name: "Shared",
      pattern: "src/shared/**",
      errorMessage:
        "`shared` is the bottom layer - it may only import from `shared`. This import points upward. 🔥",
      allowImportsFrom: ["src/shared/**"],
    },
    {
      name: "Feature",
      pattern: "src/features/**",
      errorMessage:
        "A feature may import `shared`, its own files, and a sibling feature only through its top-level `index.ts`. 🔥",
      allowImportsFrom: [
        "{family_3}/**",
        "src/features/*/index.ts",
        "src/shared/**",
      ],
    },
    {
      name: "App",
      pattern: "src/app/**",
      errorMessage:
        "`app` composes features through their `index.ts`; a deep import is allowed only for `*.page.tsx` (the `react-router` `lazy()` exception). 🔥",
      allowImportsFrom: [
        "src/app/**",
        "src/features/*/index.ts",
        "src/features/*/*.page.tsx",
        "src/shared/**",
      ],
    },
  ],
});
