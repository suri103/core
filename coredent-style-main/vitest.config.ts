import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  define: {
    'process.env.NODE_ENV': JSON.stringify('test'),
  },
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    pool: "threads",
    maxWorkers: 4,
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    testTimeout: 30000, // Coverage instrumentation can make UI renders significantly slower in CI.
    hookTimeout: 30000,
    // Test coverage thresholds
    coverage: {
      provider: "v8",
      reporter: ["text", "json", "html", "lcov"],
      excludeAfterRemap: true,
      exclude: [
        "**/node_modules/**",
        "**/coverage/**",
        "**/dist/**",
        "**/dev-dist/**",
        "**/public/**",
        "**/*.config.{js,ts}",
        "src/test/**",
        "src/types/**",
        "**/*.{test,spec}.{ts,tsx}",
        "**/*.d.ts",
      ],
      thresholds: {
        statements: 80,
        branches: 80,
        functions: 80,
        lines: 80,
      },
    },
  },
  resolve: {
    alias: [
      { find: /^@\//, replacement: path.resolve(__dirname, "./src") + "/" },
      {
        find: /^virtual:pwa-register(?:\/react)?$/,
        replacement: path.resolve(__dirname, "./src/test/mocks/pwaRegister.ts"),
      },
    ],
  },
});
