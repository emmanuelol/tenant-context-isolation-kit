# Contributing to tenant-context-isolation-kit

Contributions are welcome! Please adhere to the following principles:

## Architectural & Security Standards
1. **Clean-Room Isolation:** Code must contain zero organization-specific strings, hardcoded IDs, or internal secrets.
2. **Deterministic Verification:** Every PR must pass `make test`, `make check-blacklist`, and `make audit`.
3. **Immutability First:** Context structures must remain frozen dataclasses to prevent cross-worker state corruption.
4. **Resilience & Bounds:** Network calls must declare bounded timeouts and use exponential backoff to prevent hanging threads.
