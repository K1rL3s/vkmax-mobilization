import { createFolderStructure } from "eslint-plugin-project-structure";

const files = [
  { name: "index.ts" },
  { name: "{kebab-case}.page.tsx" },
  { name: "{kebab-case}.mock.ts" },
  { name: "{kebab-case}.tsx" },
  { name: "{kebab-case}.ts" },
  { name: "{kebab-case}.module.css" },
  { name: "{kebab-case}.svg" },
  { name: "{kebab-case}.yaml" },
];

export const folderStructureConfig = createFolderStructure({
  structureRoot: "src",
  structure: [
    { name: "{kebab-case}.d.ts" },
    {
      name: "app",
      children: [
        { name: "{kebab-case}.tsx" },
        { name: "{kebab-case}.ts" },
        { name: "{kebab-case}.module.css" },
      ],
    },
    { name: "features", children: [{ ruleId: "feature" }] },
    {
      name: "shared",
      children: [{ name: "{kebab-case}.d.ts" }, { ruleId: "group" }],
    },
  ],
  rules: {
    feature: {
      name: "{kebab-case}",
      children: [...files, { ruleId: "group" }, { ruleId: "subFeature" }],
    },
    subFeature: {
      name: "{kebab-case}",
      folderRecursionLimit: 3,
      enforceExistence: "index.ts",
      children: [...files, { ruleId: "group" }, { ruleId: "subFeature" }],
    },
    group: {
      name: "(ui|model|domain|lib|api)",
      children: [...files, { ruleId: "module" }],
    },
    module: {
      name: "{kebab-case}",
      folderRecursionLimit: 2,
      enforceExistence: "index.ts",
      children: [...files, { ruleId: "module" }],
    },
  },
});
