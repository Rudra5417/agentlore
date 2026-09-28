# AGENTS.md

<!-- rmem:begin (generated from .memory/ - do not edit) -->
## House rules

- **Use httpx, never requests** `src/api/**`
  httpx is already a dependency and supports the async client we use in handlers.
- **HTTP handlers live in src/api/handlers/** `src/api/**`
  One module per resource. Do not add handlers next to the app entrypoint.

<!-- rmem:end -->
