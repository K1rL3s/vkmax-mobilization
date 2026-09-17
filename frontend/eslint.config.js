import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";
import { defineConfig, globalIgnores } from "eslint/config";
import {
  projectStructurePlugin,
  projectStructureParser,
} from "eslint-plugin-project-structure";

import { folderStructureConfig } from "./eslint/folder-structure.ts";
import { independentModulesConfig } from "./eslint/independent-modules.ts";

export default defineConfig([
  globalIgnores(["dist"]),
  {
    files: ["**/*.{ts,tsx,js,jsx,css,svg,yaml,yml}"],
    plugins: { "project-structure": projectStructurePlugin },
    languageOptions: { parser: projectStructureParser },
    rules: {
      "project-structure/folder-structure": ["error", folderStructureConfig],
    },
  },
  {
    files: ["**/*.{ts,tsx}"],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
    },
    plugins: { "project-structure": projectStructurePlugin },
    rules: {
      "project-structure/independent-modules": [
        "error",
        independentModulesConfig,
      ],
    },
  },
]);
