# AI Quickstart

Aksara's AI surfaces are built in, but paid providers are optional for first launch.

## Check AI Hub

```bash
aksara ai-hub status
aksara ai-hub doctor
```

## Configure a Provider

```bash
aksara ai-hub configure
```

Use environment variables for secrets. Do not commit keys.

```bash
export OPENAI_API_KEY=your-key-here
export ANTHROPIC_API_KEY=your-key-here
export AZURE_OPENAI_API_KEY=your-key-here
```

## Local-First With Ollama

```bash
ollama serve
ollama pull llama3
export OLLAMA_BASE_URL=http://127.0.0.1:11434
aksara ai-hub configure
```

Tests and examples do not require this model to exist. This path is for developers who want local AI without a paid provider.

## Try AI Console

Open:

```text
http://127.0.0.1:8000/studio/ui
```

Ask:

```text
Explain my models
Review this architecture
Investigate this project
```

## Try Investigations

```bash
aksara ai investigate "Find the riskiest parts of this project"
aksara ai briefing
```

Daily Briefing and deeper investigations work best after a provider is configured, but the rest of Studio remains useful without one.
