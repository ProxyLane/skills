# Repository agent guide

This public repository publishes reusable ProxyLane skills. Everything in it
must be safe to distribute outside the private infrastructure workspace.

## Working rules

- Never include credentials, customer data, private hostnames, private
  repository assumptions, or workstation-specific paths.
- Keep each skill's `SKILL.md` concise: use a discriminating description,
  progressive disclosure, and only the scripts, references, or assets needed
  to execute the workflow reliably.
- Examples must use placeholders and safe, reproducible commands.
- Keep `README.md` synchronized when it duplicates or catalogs skill content.
- Validate frontmatter, referenced paths, shell/code examples, and any supplied
  scripts before publishing. Inspect the final diff for accidental private
  context because this repository is public.
