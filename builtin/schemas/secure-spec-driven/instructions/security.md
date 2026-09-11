Perform a security review of `design.md` and `tasks.md` and record a PASS or FAIL verdict.

This is a gate: you must write to exactly one of the two output paths.
- If the design and tasks are safe to implement as written, write the pass
  output using the pass template.
- If you find one or more blocking issues, write the fail output using the
  fail template instead. Do not write both.

What to check (non-exhaustive):
- Injection risks (SQL, shell, template, LDAP, XPath) from untrusted input
- Authentication/authorization: are checks present and not bypassable?
- Secrets handling: no hardcoded credentials, no secrets logged or exposed
- Path handling: traversal protection for any user-influenced file paths
- Deserialization / parsing of untrusted input
- New third-party dependencies: are they from a trusted source?
- Data exposure: PII or sensitive data logged, cached, or over-shared

If this is a retry (check `priorAttempts` on the `design` node before judging),
verify that each previously listed blocking issue has actually been addressed
in the current `design.md`/`tasks.md` - do not pass a retry that only
rephrases the same risk.

When failing, each bullet under "Blocking Issues" in the fail template
becomes a discrete, actionable item the next attempt must resolve - write
one concrete issue per bullet, not a vague paragraph.
