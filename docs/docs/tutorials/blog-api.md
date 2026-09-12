# Build a blog-shaped API

Start with the [ticket-desk tutorial](../getting-started/first-project.md) to
learn Aksara's complete model → migration → protected REST → test workflow.
Then inspect the [Blog example](https://github.com/nagarjuna-tella/Aksara/tree/main/examples/blog)
for Post/Comment relationships and custom publishing actions.

This page merges the older standalone blog tutorial into the canonical learning
path. The old tutorial promised a complete registration/login application while
mixing legacy request/serializer APIs and incomplete authentication wiring.
Those snippets are no longer the recommended implementation.

## Transfer the concepts

| Blog requirement | Where to learn the implementation |
| --- | --- |
| Persist posts and comments | [Models](../orm/models.md) and [migrations](../orm/migrations.md) |
| Relate a comment to its post | [Ticket-desk relations](ticket-desk.md) and [relations reference](../orm/relations.md) |
| Generate CRUD endpoints | [First project](../getting-started/first-project.md) and [ViewSets](../api/viewsets.md) |
| Validate titles and content | [Serializer validation](ticket-desk.md) |
| Identify the caller | [Authentication](../api/authentication.md) and the first-project identity adapter |
| Restrict publishing or editing | [Permissions](../api/permissions.md) and [custom actions](../api/actions.md) |
| Separate customer workspaces | [Tenant isolation](ticket-desk-tenancy.md) |
| Queue a report or notification | [Background reports](ticket-desk-reports.md) |
| Reauthorize delayed actions | [Durable actions](ticket-desk-durable.md) |

An author relationship stores a reference; it does not by itself verify the
requesting user's identity or authorize editing. Decide explicitly whether
posts are public to read, whether authors may edit only their own posts, and
which role may publish. Apply those rules to custom actions as well as CRUD.

## Run the supplementary example

The repository Blog README supplies its exact package entry point and migration
commands. The example contains `Post` and `Comment`; it is not a complete user
registration or production publishing system. Its API-key helper does not
establish a Principal for generated writes, so the historical unauthenticated
seed POST is denied. Do not remove permissions to make that request succeed.

Use the canonical tutorial's verified identity integration when adapting the
pattern. Replace its local token mapping with your actual identity service
before exposing an application publicly. Test successful create/update/delete,
input rejection, anonymous denial and denied edits by another author.

The [example catalog](../getting-started/examples.md) distinguishes startup
checks from complete authenticated application tests. Follow the
[production guide](deployment.md) before deploying your adaptation.
