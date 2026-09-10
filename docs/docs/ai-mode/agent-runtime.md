# Agent Runtime

!!! warning "Experimental and process-local"
    Agent runtime and planner interfaces are experimental in v0.6. Investigation
    and session state does not survive process restart or provide multi-worker
    continuity. The framework does not guarantee durable approvals, replay,
    exactly-once tool effects, or authorization revalidation after restart.

Execute bounded AI-agent experiments that can use tools and complete multi-step
tasks under application-controlled approval and authorization.

---

## Overview

The Agent Runtime executes AI agents that can:

- **Use tools** to interact with your codebase
- **Plan and execute** multi-step tasks
- **Iterate** based on results
- **Handle errors** and recover

```python
from aksara.ai import AgentRuntime

runtime = AgentRuntime()
result = await runtime.execute("Review the User model and suggest improvements")
```

---

## Quick Start

### Basic Execution

```python
from aksara.ai import AgentRuntime

runtime = AgentRuntime()

result = await runtime.execute(
    "Find all models without indexes and suggest additions"
)

print(result.output)      # Agent's response
print(result.actions)     # Tools the agent used
print(result.suggestions) # Suggestions if any
```

### With Tools

```python
result = await runtime.execute(
    "Create a Comment model for blog posts",
    tools=["create_model", "create_migration"],
)
```

### Interactive Mode

```python
result = await runtime.execute(
    "Refactor the User model",
    interactive=True,  # Confirm before each action
)
```

---

## Agent Capabilities

### Code Analysis

```python
result = await runtime.execute(
    "Analyze the codebase for security issues"
)

print(result.findings)
# [
#     {"severity": "high", "issue": "SQL injection in...", "fix": "..."},
#     {"severity": "medium", "issue": "Missing input validation...", "fix": "..."},
# ]
```

### Code Generation

```python
result = await runtime.execute(
    "Create a REST API for the Product model with full CRUD"
)

print(result.created_files)
# ["serializers/product.py", "viewsets/product.py", "tests/test_product_api.py"]
```

### Code Modification

```python
result = await runtime.execute(
    "Add soft delete to all models"
)

print(result.modified_files)
# ["models/user.py", "models/post.py", "models/comment.py"]
```

### Data Operations

```python
result = await runtime.execute(
    "Find users who haven't logged in for 90 days and export to CSV"
)

print(result.output_file)  # "inactive_users.csv"
```

---

## Tool Configuration

### Available Tools

```python
runtime = AgentRuntime(
    tools=[
        # Data tools
        "query_records",
        "create_record",
        "update_record",
        "delete_record",
        
        # Schema tools
        "list_models",
        "describe_model",
        "suggest_migration",
        
        # Code tools
        "generate_model",
        "generate_viewset",
        "generate_test",
        "patch_file",
        
        # System tools
        "run_command",
        "read_file",
        "write_file",
    ]
)
```

### Restrict Tools

```python
# Read-only agent
runtime = AgentRuntime(
    tools=["query_records", "list_models", "describe_model", "read_file"],
    allow_writes=False,
)
```

### Custom Tools

```python
from aksara.ai.tools import Tool, register_tool

@register_tool
class DeployTool(Tool):
    name = "deploy"
    description = "Deploy the application"
    
    async def execute(self, environment: str):
        # Deploy logic
        return {"status": "deployed", "url": "..."}

runtime = AgentRuntime(
    tools=["deploy"],  # Include custom tool
)
```

---

## Execution Modes

### Single Task

```python
result = await runtime.execute("Add email validation to User model")
```

### Conversation Mode

```python
# Multi-turn conversation
session = runtime.start_session()

result1 = await session.send("What models exist in the codebase?")
result2 = await session.send("Add a phone field to User")
result3 = await session.send("Now create a migration for that change")

await session.end()
```

### Autonomous Mode

```python
# Agent works autonomously on a goal
result = await runtime.execute(
    goal="Improve test coverage to 80%",
    mode="autonomous",
    max_iterations=50,
)
```

### Supervised Mode

```python
# Agent proposes, human approves
result = await runtime.execute(
    "Refactor the API layer",
    mode="supervised",
    approval_callback=my_approval_function,
)
```

---

## Result Handling

### Result Object

```python
result = await runtime.execute(task)

# Core properties
print(result.success)       # True/False
print(result.output)        # Agent's final response
print(result.error)         # Error message if failed

# Execution details
print(result.iterations)    # Number of think-act cycles
print(result.actions)       # List of tool calls
print(result.duration_ms)   # Total execution time

# Artifacts
print(result.created_files)    # Files created
print(result.modified_files)   # Files modified
print(result.suggestions)      # Suggestions for user
```

### Action Log

```python
for action in result.actions:
    print(f"Tool: {action.tool}")
    print(f"Input: {action.input}")
    print(f"Output: {action.output}")
    print(f"Duration: {action.duration_ms}ms")
```

### Streaming Results

```python
async for event in runtime.execute_stream(task):
    if event.type == "thinking":
        print(f"Agent thinking: {event.content}")
    elif event.type == "action":
        print(f"Agent using tool: {event.tool}")
    elif event.type == "result":
        print(f"Tool result: {event.result}")
    elif event.type == "complete":
        print(f"Final output: {event.output}")
```

---

## Error Handling

### Automatic Recovery

```python
runtime = AgentRuntime(
    retry_on_error=True,
    max_retries=3,
)

result = await runtime.execute(task)
# Agent will retry failed tool calls
```

### Error Handling Strategies

```python
runtime = AgentRuntime(
    error_strategy="retry",    # Retry the action
    # or "skip",               # Skip and continue
    # or "abort",              # Stop execution
    # or "ask",                # Ask user
)
```

### Custom Error Handler

```python
async def my_error_handler(error, context):
    if isinstance(error, RateLimitError):
        await asyncio.sleep(60)
        return "retry"
    return "abort"

runtime = AgentRuntime(
    error_handler=my_error_handler,
)
```

---

## Resource Limits

### Token Limits

```python
runtime = AgentRuntime(
    max_input_tokens=8000,
    max_output_tokens=4000,
    max_total_tokens=100000,  # Per session
)
```

### Iteration Limits

```python
runtime = AgentRuntime(
    max_iterations=20,        # Think-act cycles
    max_tool_calls=50,        # Total tool invocations
)
```

### Time Limits

```python
runtime = AgentRuntime(
    timeout_seconds=300,      # 5 minute timeout
    tool_timeout_seconds=30,  # Per-tool timeout
)
```

---

## Callbacks and Hooks

### Before/After Tool

```python
async def before_tool(tool_name, params):
    print(f"About to call {tool_name}")
    return True  # Allow, or False to block

async def after_tool(tool_name, result):
    print(f"{tool_name} returned: {result}")

runtime = AgentRuntime(
    before_tool=before_tool,
    after_tool=after_tool,
)
```

### Progress Callback

```python
async def on_progress(event):
    print(f"[{event.iteration}/{event.max_iterations}] {event.status}")

runtime = AgentRuntime(
    progress_callback=on_progress,
)
```

### Approval Callback

```python
async def approve_action(tool_name, params):
    print(f"Agent wants to {tool_name} with {params}")
    response = input("Allow? [y/N] ")
    return response.lower() == "y"

runtime = AgentRuntime(
    approval_callback=approve_action,
)
```

---

## CLI Usage

### Execute Task

```bash
aksara ai agent "Review code for issues"
```

### Interactive Session

```bash
aksara ai agent --interactive

> What models exist?
Agent: I found 5 models: User, Post, Comment, Tag, Category...

> Add a slug field to Post
Agent: I'll add a slug field to the Post model...
  - Modified models/post.py
  - Created migration 0006_add_post_slug.py

> Exit
```

### With Tool Restrictions

```bash
aksara ai agent "Analyze models" --tools query_records,list_models,describe_model
```

---

## Configuration

```python
# settings.py
AKSARA = {
    "AI_AGENT_RUNTIME": {
        # Model
        "model": "<provider-model-name>",
        "temperature": 0.1,
        
        # Tools
        "default_tools": ["query_records", "list_models", "describe_model"],
        "allow_write_tools": True,
        "allow_system_tools": False,
        
        # Limits
        "max_iterations": 20,
        "max_tool_calls": 50,
        "timeout_seconds": 300,
        "max_total_tokens": 100000,
        
        # Safety
        "require_approval_for": ["delete_record", "run_command"],
        "sandbox_mode": False,
        
        # Logging
        "log_actions": True,
        "log_reasoning": False,
    },
}
```

---

## Examples

### Code Review Agent

```python
result = await runtime.execute(
    "Review the Post model and suggest improvements",
    tools=["describe_model", "read_file"],
)

print(result.suggestions)
# [
#     "Add index on created_at for faster queries",
#     "Consider adding slug field for SEO-friendly URLs",
#     "Add unique constraint on (author, title)",
# ]
```

### Migration Helper Agent

```python
result = await runtime.execute(
    "Check for pending migrations and create them",
    tools=["list_models", "suggest_migration", "write_file"],
)
```

### Test Generator Agent

```python
result = await runtime.execute(
    "Generate tests for all untested models",
    tools=["list_models", "describe_model", "generate_test", "write_file"],
)
```

---

## Best Practices

### 1. Be Specific

```python
# Less effective
await runtime.execute("Fix the code")

# More effective
await runtime.execute(
    "Find and fix N+1 query issues in the PostViewSet"
)
```

### 2. Restrict Tools Appropriately

```python
# For analysis tasks, use read-only tools
runtime = AgentRuntime(
    tools=["query_records", "list_models", "read_file"],
)
```

### 3. Use Supervised Mode for Sensitive Operations

```python
result = await runtime.execute(
    "Clean up duplicate users",
    mode="supervised",  # Requires approval
)
```

---

## Related Documentation

- [AI Mode Overview](index.md)
- [Tools](tools.md)
- [Planner](planner.md)
- [Safety](safety.md)
