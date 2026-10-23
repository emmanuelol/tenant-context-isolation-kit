## Description

Please provide a concise summary of the changes and the architectural motivation.

---

## Type of Change

- [ ] 🐛 Bug fix (non-breaking change fixing an issue)
- [ ] ✨ New feature (non-breaking change adding functionality)
- [ ] ⚠️ Breaking change (fix or feature causing existing behavior to change)
- [ ] 📝 Documentation update
- [ ] 🧪 Test suite enhancement / Concurrency fuzzing

---

## Isolation & Security Impact

Does this change touch tenant context resolution, client isolation, or database query generation?
- [ ] Yes: Document how cross-tenant isolation and fail-closed guarantees are preserved.
- [ ] No: Pure utility/tooling change.

---

## Checklist

- [ ] Code adheres to project style guidelines (`ruff check`, `ruff format`).
- [ ] Added unit tests verifying positive and fail-closed behaviors.
- [ ] Concurrency and context-bleed tests passing (`pytest tests/test_concurrency_isolation.py`).
- [ ] Documentation / ADR updated if architectural patterns changed.
- [ ] All CI checks passing locally.
