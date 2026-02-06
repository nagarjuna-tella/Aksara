# Glossary

Common terms used in Aksara documentation.

---

## A

### Action
A custom endpoint on a ViewSet, defined with the `@action` decorator. Actions can be detail routes (operating on a single object) or list routes (operating on the collection).

### AI Mode
Aksara's integrated AI-powered development features including natural language queries, code generation, and intelligent debugging.

### Agent
An AI agent that can execute multi-step tasks using tools. See [Agent Runtime](ai-mode/agent-runtime.md).

### Annotation
Adding computed values to queryset results, typically using aggregate functions like `Count`, `Sum`, `Avg`.

### Authentication
The process of verifying user identity. Aksara supports token-based and custom authentication backends.

---

## B

### Backend
A pluggable component that handles specific functionality. Examples: cache backend, authentication backend.

### Bulk Operations
Database operations that affect multiple records at once (`bulk_create`, `bulk_update`).

---

## C

### Cache
Temporary storage for frequently accessed data to improve performance. Aksara supports memory and Redis backends.

### Codegen
AI-powered code generation for models, viewsets, serializers, and tests.

### Context Engine
Component that gathers relevant code context for AI operations.

### CRUD
Create, Read, Update, Delete — the four basic operations for persistent storage.

---

## D

### Decorator
A Python pattern that wraps functions or classes. Aksara uses decorators for actions, caching, signals, etc.

### Defer
Loading a model instance without specific fields, loading them on-demand when accessed.

### Detail Route
A ViewSet endpoint that operates on a single object, using the lookup field (usually `id`).

---

## E

### Eager Loading
Loading related objects along with the main query to avoid N+1 queries. See `select_related` and `prefetch_related`.

### Endpoint
A URL path that accepts HTTP requests and returns responses.

---

## F

### Field
A class that defines a database column and its behavior. Examples: `String`, `Integer`, `ForeignKey`.

### Filter
Constraining queryset results based on field values.

### FilterSet
A class that defines available filters for a ViewSet.

### Foreign Key (FK)
A database relationship where one model references another model's primary key.

---

## G

### Generator
A Python construct that yields values lazily. Used in async iteration over querysets.

---

## H

### Handler
A function that responds to events (signals) or processes requests.

### Hook
A point in the lifecycle where custom code can be executed. Example: `pre_save`, `post_delete`.

---

## I

### Index
A database structure that improves query performance on specific columns.

### Instance
A single object of a model class.

### Installed Apps
The list of applications registered in Aksara settings.

---

## J

### JSON Field
A field that stores JSON data, allowing nested structures.

### JWT
JSON Web Token — a compact, URL-safe token format used for authentication.

---

## K

### Key (Primary)
The unique identifier for a model instance, usually a UUID.

---

## L

### Lazy Loading
Deferring data loading until it's actually needed.

### List Route
A ViewSet endpoint that operates on the entire collection of objects.

### Lookup
A query operator that specifies how to match values. Example: `exact`, `contains`, `gt`.

---

## M

### Manager
A class that provides the database query interface for a model (`Model.objects`).

### Many-to-Many (M2M)
A relationship where multiple instances of one model can be related to multiple instances of another.

### Meta
An inner class on models and serializers that defines configuration options.

### Middleware
Code that processes requests and responses globally, before and after view handling.

### Migration
A file that describes database schema changes, allowing version control of the database structure.

### Model
A Python class that represents a database table.

### ModelAdmin
Configuration class for displaying a model in the admin interface.

### ModelSerializer
A serializer that automatically generates fields from a model definition.

### ModelViewSet
A ViewSet that provides complete CRUD operations for a model.

---

## N

### N+1 Problem
A performance issue where querying N related objects results in N+1 database queries instead of 1-2.

---

## O

### ORM
Object-Relational Mapping — the system that maps Python objects to database tables.

### Only
Loading a model instance with only specific fields, ignoring others.

---

## P

### Pagination
Dividing large result sets into smaller pages.

### Patch Engine
AI component that applies code modifications safely with preview and rollback.

### Permission
A class that determines whether a user can perform an action.

### Prefetch Related
Loading reverse foreign key or many-to-many relations efficiently using a separate query.

### Primary Key (PK)
The unique identifier field for a model instance.

---

## Q

### Query
A request to retrieve or modify data in the database.

### Query Engine
AI component that converts natural language to database queries.

### QuerySet
An object representing a database query that can be chained and lazily evaluated.

---

## R

### Read-Only
A serializer or field that can only output data, not accept input.

### Related Name
The attribute name for accessing related objects from the reverse side of a relationship.

### Request
An object containing information about an HTTP request (method, headers, body, user).

### Response
An object containing information about an HTTP response (status, headers, body).

### Router
A component that maps URL patterns to ViewSet actions.

---

## S

### Schema Doctor
AI tool that analyzes database schema and suggests improvements.

### Select Related
Loading foreign key relations efficiently using a JOIN query.

### Serializer
A class that converts between Python objects and JSON (and validates input).

### Signal
A notification sent when certain events occur, allowing decoupled code to respond.

### Slug
A URL-friendly string, typically derived from a title (e.g., "hello-world").

---

## T

### Tenant
An organization or customer in a multi-tenant application.

### Throttling
Rate limiting to prevent abuse of API endpoints.

### Through Model
An intermediate model in a many-to-many relationship for storing extra data.

### Token
A string used to authenticate API requests.

### Transaction
A group of database operations that succeed or fail together.

---

## U

### UUID
Universally Unique Identifier — Aksara uses UUIDs as default primary keys.

---

## V

### Validation
Checking that data meets required criteria before processing.

### ValidationError
An exception raised when data fails validation.

### ViewSet
A class that groups related API endpoints (list, create, retrieve, update, delete, custom actions).

---

## W

### Write-Only
A serializer field that can only accept input, not appear in output (e.g., passwords).

---

## Related

- [Getting Started](getting-started/index.md)
- [ORM Guide](orm/index.md)
- [API Guide](api/index.md)
