import { defineConfig } from "@neon/config/v1";

export default defineConfig({
  // PostgreSQL is included on every Neon branch. This app uses FastAPI and
  // Psycopg; no browser database client or additional Neon service is needed.
  // Branch policy: per-branch tuning
  branch: (branch) => {
    if (branch.isDefault) {
      // Default branch: no overrides, uses project defaults
      return {};
    }
    if (!branch.exists) {
      // New non-default branches: auto-expire
      // Run `neon checkout <name>` to create a new branch with these settings
      return { ttl: "7d" };
    }
    // Existing branch: no changes
    return {};
  },
});
