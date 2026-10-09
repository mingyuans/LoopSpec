# Security Review: FAIL

## Blocking Issues

- Plan-integrity gap: the proposed `planDigest` covers the effective schema and fragment metadata but not the actual instruction and template bytes copied into the snapshot. A source resource could change after the human reviews the digest yet before materialization without invalidating approval. Include canonical content hashes for every resolved instruction/template in the digest, read each source resource once into a validated in-memory bundle, and materialize exactly those buffered bytes.

## Scope Reviewed

- `design.md`
- `tasks.md`
- Fragment and composition requirements covering untrusted YAML, path resolution, digest binding, resource copying, metadata activation, recomposition, and profiles

## Recommended Fix Direction

Define a resolved composition bundle whose canonical digest includes node definitions plus the relative destination and SHA-256 of every materialized resource. Validation, approval checking, and materialization must all consume the same bundle so no second filesystem read can substitute different bytes.
