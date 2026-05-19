# Studio Quickstart

Studio is the built-in project inspector available in local development.

## Start the App

```bash
aksara doctor launch-check
aksara migrate
aksara dev
```

## Open Studio

```text
http://127.0.0.1:8000/studio/ui
```

Studio helps you inspect:

- Models and fields
- Routes and ViewSets
- Query activity
- Migration health
- MCP tool output
- AI Console context
- Project Graph
- AI Debugger, Architecture Review, Performance Analyzer, Investigation Sessions, and Daily Briefing when AI is configured

## First-Run States

If something is missing, Studio and `aksara doctor launch-check` should tell you the next action:

- No database configured: set `DATABASE_URL` or run `aksara dbsetup`.
- No migrations run: run `aksara migrate`.
- No AI provider configured: continue using non-AI Studio tools or run `aksara ai-hub configure`.
- No graph built yet: open Project Graph or start an investigation.

AI provider setup is optional for first launch.
