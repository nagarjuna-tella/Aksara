# AI code generation

!!! warning "Experimental"
    Code generation and patch application are outside the stable v0.7
    contract. Aksara does not expose a `Codegen` class.

The real deterministic API accepts a structured model specification and returns
files for review:

```python
from aksara.ai.codegen import (
    AiCodegenRequest,
    AiFieldSpec,
    AiModelSpec,
    generate_code,
)

spec = AiModelSpec(
    app_label="app",
    name="Comment",
    fields=[
        AiFieldSpec(name="text", type="text"),
        AiFieldSpec(name="approved", type="boolean", default=False),
    ],
)
result = generate_code(AiCodegenRequest(target="model", model_spec=spec))

for path, source in result.files.items():
    print(path)
    print(source)
```

Aksara does not infer this specification from prose. An external agent may
produce it, but the application owns model/provider selection and review.
Generated output is not written automatically; inspect it, run normal
migrations and tests, and use source control.

See [Patch engine](patch-engine.md) for the separate experimental validation and
application functions.
