import baseConfig from "./packages/config/eslint/base.mjs";

export default [
  ...baseConfig,
  {
    ignores: [
      "node_modules/**",
      "dist/**",
      "build/**",
      ".next/**",
      "coverage/**",
      "services/**/migrations/**"
    ]
  }
];
