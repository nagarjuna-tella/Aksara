# Your first 10 minutes

Use [First project: a ticket desk](first-project.md) for the complete runnable
instructions. It starts with an empty directory and introduces one model,
generated REST, PostgreSQL migrations, local authentication and tests.

Begin with the [installation and project setup](first-project.md):

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install "aksara-framework==0.7.0"
aksara startproject ticket_desk
cd ticket_desk
aksara dbsetup
```

Then copy the guide's exact model, ViewSet, routes and authentication adapter.
Follow its migration, server and test commands. These setup commands alone do
not create the ticket API. The guide also explains Doctor's optional-feature
warnings so you do not have to enable Studio or an AI provider to proceed.

Once the REST tests pass, continue with
[relations and validation](../tutorials/ticket-desk.md). Tenant isolation,
background reports, durable actions and optional MCP access build on that same
application in later chapters. The generated project keeps MCP, provider-backed
AI and Studio disabled by default.
