# Planner

!!! warning "Experimental"
    Aksara 0.7.0rc1 does not define or export a `Planner` class. The plan schemas
    and deterministic handlers described here are functional but evolving.

The real planning surface is `AiPlan` plus `AiPlanStep`. External code creates
the plan. Aksara validates its shape and can execute known step handlers.

```python
from aksara.ai.planner import AiPlan, AiPlanStep, validate_plan

plan = AiPlan(
    intent="Inspect application health",
    steps=[
        AiPlanStep(
            id="health",
            type="run_health_check",
            description="Check the running application",
        )
    ],
)

assert validate_plan(plan) == []
```

To execute this experimental plan against an application:

```python
from aksara.ai.limits import AgentRuntimeLimits
from aksara.ai.planner import execute_plan

result = await execute_plan(
    app,
    plan,
    dry_run=True,
    limits=AgentRuntimeLimits(max_steps=5, run_timeout_seconds=30),
)
print(result.success)
```

Import `execute_plan` from `aksara.ai.planner` for this API. The top-level
`aksara.ai.execute_plan` name belongs to the separate experimental investigation
orchestrator and accepts a different plan type.

## What the planner does

- validates plan step IDs, dependencies, and known step types;
- rejects cycles;
- sorts dependencies deterministically;
- runs registered handlers with step and overall time limits;
- stops after the first failed step; and
- supports preview behavior where the underlying handler implements it.

Some handlers can inspect an application or produce deterministic artifacts.
Code generation and patch application are experimental, and generated test
steps still contain incomplete behavior. Review every preview before applying
changes.

The planner does not call an LLM, choose goals, persist a session, resume after
restart, or provide a stable autonomous workflow contract.
