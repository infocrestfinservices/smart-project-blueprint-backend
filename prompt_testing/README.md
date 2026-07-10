# prompt_testing

This folder is a **completely isolated testing workspace** for prompt engineering and AI experimentation.

It is fully separate from the production `backend` and `frontend`. Nothing here is imported, executed, or referenced by the main application — it exists purely as a sandbox for iterating on AI prompts **before** they are integrated into the main codebase.

## Purpose

- Draft, refine, and compare AI prompts in isolation.
- Validate model inputs/outputs against expected schemas.
- Capture experimental results without touching production code.

## Structure

```
prompt_testing/
├── prompts/   # Draft and candidate prompts under test
├── schemas/   # Expected input/output schemas for validation
├── outputs/   # Captured results from prompt experiments
└── README.md  # This file
```

## Ground rules

- This workspace does **not** modify or depend on `backend` or `frontend`.
- Changes here have **no effect** on routers, services, agents, templates, APIs,
  database models, authentication, or configuration.
- Promote a prompt to the main application only after it has been tested here.
