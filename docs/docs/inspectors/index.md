# Inspectors

Use inspectors for developer diagnostics. They describe model declarations and
process-local query traces; they do not certify the deployed database schema or
production performance.

- [Inspect model declarations](models.md): fields, forward relationships and
  inferred constraints for registered Python models.
- [Inspect query statistics and plan limitations](query.md): trace summaries and
  the distinction between real PostgreSQL plans and synthetic output.
- [Profile actual queries](../debugging/query-profiling.md): the supported
  database-backed workflow for investigating performance.

Studio and AI consumers may display this metadata, but those experimental
interfaces do not strengthen its guarantees. Keep diagnostic output private:
it can contain schema names, SQL, and application details.
