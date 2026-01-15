import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  {
    files: ["**/*.{js,jsx,ts,tsx}"],
    ignores: ["eslint.config.mjs", "*.config.{js,mjs,ts}"],
    rules: {
      // Allow underscore-prefixed variables to be unused (convention for intentionally unused params)
      "@typescript-eslint/no-unused-vars": [
        "warn",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          caughtErrorsIgnorePattern: "^_",
        },
      ],
      // Custom rule: Prevent hardcoded Tailwind color utilities
      "no-restricted-syntax": [
        "error",
        {
          selector:
            "Literal[value=/\\b(gray|slate|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-(50|100|200|300|400|500|600|700|800|900|950)\\b/]",
          message:
            "Use design tokens instead of hardcoded Tailwind colors. Reference tokens like bg-surface, text-text, border-border, etc.",
        },
        {
          selector:
            "Literal[value=/\\b(bg-white|bg-black|text-white|text-black)\\b/]",
          message:
            "Use design tokens instead of bg-white/bg-black. Use bg-bg, text-text, etc.",
        },
      ],
    },
  },
]);

export default eslintConfig;
