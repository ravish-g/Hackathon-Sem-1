# Backend workstream ownership

The four feature branches are isolated after the foundation commit:

- `build-apis`: REST, serializers, selectors, migrations only when coordinated,
  and worker ingestion.
- `process-feeds`: all `vision/**` and `benchmarks/**` implementation.
- `predict-risk`: risk, telemetry, calibration and incident services.
- `stream-events`: Channels consumer, routing and publisher.

No workstream edits frontend files. Shared model or contract changes require
coordination before implementation and must preserve acknowledgement versus
resolution semantics.
