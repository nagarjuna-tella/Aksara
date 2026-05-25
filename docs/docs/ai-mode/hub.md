# AI Hub

The **AI Hub** is Aksara's unified AI provider management interface. It provides a single pane of glass for configuring, monitoring, and using AI providers across your Aksara application.

## Overview

The AI Hub consolidates all AI provider management into one place:

- **Provider Detection** — Auto-detect configured providers from environment variables
- **Provider Configuration** — Set up new providers via UI, CLI, or programmatically
- **Connectivity Testing** — Ping providers to verify API keys and network access
- **Agent Interface** — Run prompts against any configured provider with project context

## Accessing the AI Hub

### Studio UI

Navigate to **AI Hub** in the Studio sidebar, or press the `A` key.

The Hub has 4 tabs:

| Tab | Purpose |
|-----|---------|
| **Providers** | View/configure/test AI providers |
| **Tools** | Links to AI Helpers, Profiles, Agent, Inspector |
| **Context Viewer** | Browse project context sections with size badges |
| **Agent** | Run prompts with model selection and context injection |

### CLI

```bash
aksara ai-provider list          # List all detected providers
aksara ai-provider detect        # Auto-detect from environment
aksara ai-provider ping          # Test connectivity
aksara ai-provider configure openai --api-key <API_KEY>
```

### API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/studio/ai/hub/providers` | Provider status & detection |
| POST | `/studio/ai/hub/providers/save` | Save provider config |
| POST | `/studio/ai/hub/providers/ping` | Test connectivity |
| POST | `/studio/ai/hub/agent/run` | Run AI agent |

## Quick Start

1. Set an environment variable:
   ```bash
   export OPENAI_API_KEY=<OPENAI_API_KEY>
   ```

2. Verify detection:
   ```bash
   aksara ai-provider detect
   ```

3. Test connectivity:
   ```bash
   aksara ai-provider ping
   ```

4. Open the AI Hub in Studio and start using the agent.

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `A` | Open AI Hub |
| `Cmd+Enter` | Run agent prompt |
