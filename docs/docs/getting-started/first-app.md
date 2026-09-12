# Your first application

Follow [First project: a ticket desk](first-project.md) for the complete
application. It replaces the earlier standalone Tasks example with a protected
Ticket API and executable tests. Use its exact files together; fragments from
different starter applications are not interchangeable.

The generated project starts with model, serializer, ViewSet, route and admin
stubs. The tutorial fills them in this order:

1. Define `Ticket` in `app/models.py`.
2. Define its authenticated ViewSet in `app/views.py`.
3. Register the ViewSet through `app/urls.py`.
4. Add the tutorial's server-owned local credential adapter.
5. Generate and apply the migration, start the app and run the tests.

A model definition does not create its database table until its migration runs.
A ViewSet does not verify credentials merely because it is registered. The
first-project guide includes both steps and explains the development-only
identity adapter.

Continue with [relations and validation](../tutorials/ticket-desk.md) when the
first API works. Optional MCP exposure comes in the
[final chapter](../tutorials/ticket-desk-mcp.md), after application authorization
and tenant boundaries are in place.
