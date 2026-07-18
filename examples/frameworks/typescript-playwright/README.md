# TypeScript Playwright Example

This example shows Playwright-style direct SDK usage from the source tree. It assumes your application test project already has Playwright installed.

Build the local TypeScript SDK first:

```bash
(cd sdk-typescript && npm ci && npm run build)
```

Then adapt `register.spec.ts` into your Playwright test suite. The import path in the example points at the repository-local build output and avoids any package publishing assumption.
