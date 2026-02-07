# Changelog

All notable changes to Aksara.

---

## [0.5.10] — 2026-02-09

### Added
- **Query Inspector & ORM Profiler**: Comprehensive database query tracing and visibility
  - **Core Tracing Layer** (`aksara/db/tracing.py`):
    - `DbQueryTrace` dataclass for individual query captures (SQL, params, timing, operation, table, call site, tags)
    - `DbQueryBatch` dataclass for per-request query collections with aggregations
    - Contextvar-based session management (`start_trace_session`, `stop_trace_session`, `record_query`)
    - In-memory ring buffer storage for recent traces (configurable max size)
    - Automatic SQL operation extraction (SELECT/INSERT/UPDATE/DELETE/etc.)
    - Automatic table name extraction from queries
    - SQL normalization for query grouping and N+1 detection
    - N+1 query pattern detection heuristics (configurable threshold)
  
  - **Request Lifecycle Integration**:
    - New `QueryTraceMiddleware` for automatic per-request tracing
    - Integration with `QueryLogger` to record all queries when tracing enabled
    - Request ID correlation via existing `request_id_var` contextvar
    - Automatic capture of HTTP method, path, and status code
  
  - **Studio Backend Endpoints**:
    - `GET /studio/db/queries` - Query inspector with stats, recent batches, slow queries
    - `GET /studio/db/queries/{request_id}` - Detailed query batch for specific request
    - New Pydantic models: `StudioQueryTrace`, `StudioQueryBatch`, `StudioQueryStats`, `StudioQueryInspector`
  
  - **Studio UI Panel**:
    - New "DB & Queries" navigation item in Studio sidebar
    - Stats cards: Total Queries, Avg Per Request, Slow Queries, N+1 Detected
    - Slowest Queries panel with SQL preview and call site info
    - Recent Requests panel with method, path, status, query count, timing
    - Warning highlights for slow queries and N+1 patterns
    - Disabled tracing banner with configuration instructions
  
  - **CLI Tools** (`aksara db` command group):
    - `aksara db stats` - Show aggregate query statistics
    - `aksara db profile` - Show detailed profile data (slow queries, recent batches)
    - `aksara db clear` - Clear stored trace data

- **Configuration Options**:
  - `db_trace_enabled` / `AKSARA_DB_TRACE_ENABLED` - Enable/disable tracing (default: False)
  - `db_trace_slow_threshold_ms` / `AKSARA_DB_TRACE_SLOW_THRESHOLD_MS` - Slow query threshold (default: 100ms)
  - `db_trace_max_queries` / `AKSARA_DB_TRACE_MAX_QUERIES` - Max queries per request (default: 500)

### Changed
- `QueryLogger` now always captures timing (not just in debug mode) for tracing integration
- CLI version bumped to 0.5.10

### Documentation
- Changelog updated with v0.5.10 Query Inspector features

---

## [0.5.9] — 2026-02-08

### Added
- **Admin UI 2.0 - DX & UX Pass**: Major admin interface overhaul
  - **Theme Toggle Button**: Visible dark/light mode toggle in header
    - Uses `localStorage` for persistence (`aksara-admin-theme`)
    - Respects `prefers-color-scheme` as default
    - Smooth icon transition between sun/moon
  - **Studio Link**: Header link to AI Studio when enabled
  - **Improved Breadcrumbs**: SVG chevron separators, aria-label support
  - **Record Count Badges**: Show count in list view headers
  - **Sticky Form Actions**: Form save/cancel/delete actions stick to bottom
  - **Search UX**: New search card with icon, clear button styling
  - **Empty States**: Improved SVG icons replacing emoji
  - **Dashboard Cards**: New `.dashboard-card` component with hover effects
  - **Model Links**: First column in list view is now clickable link to edit

- **JSON Widget Enhancements** (json_widget.js v0.5.9):
  - Auto-format JSON on blur
  - Auto-format on paste
  - JSON structure info (array/object count)
  - Improved error focus and scrolling

- **Array Widget Enhancements** (array_widget.js v0.5.9):
  - Drag-and-drop reordering
  - Drag handle with grip icon
  - Smooth remove animation
  - Enter key to add new item
  - Count badge support
  - Warning message for max items

- **Responsive Improvements**:
  - Mobile sidebar with overlay
  - Collapsible form actions
  - Mobile-friendly tables
  - Breakpoints at 1024px, 768px, 480px

### Changed
- CSS version updated to 0.5.9
- Badge for DEBUG mode changed from `badge-success` to `badge-warning`
- Form templates use `form-input` class instead of `form-control`
- Index template uses SVG icons instead of emoji
- Model list uses SVG icons in empty states and actions
- Theme localStorage key changed to `aksara-admin-theme`

### Fixed
- Theme toggle now updates icon visibility correctly on page load
- Array widget preserves value when clearing last item

### Documentation
- Admin UI 2.0 changes documented in changelog

---

## [0.5.8] — 2026-02-07

### Added
- **Example Hardening & Golden Paths**: Production-adjacent patterns for examples
- **API Key Authentication** for Blog and CRM examples:
  - New `auth.py` modules with `require_api_key` dependency
  - `X-API-Key` header authentication pattern
  - Environment variable support (`BLOG_API_KEY`, `CRM_API_KEY`)
- **Pagination & Ordering Support**:
  - `page` and `page_size` query parameters on list endpoints
  - `order_by` query parameter (prefix with `-` for descending)
  - `DEFAULT_PAGE_SIZE=10`, `MAX_PAGE_SIZE=100` settings
  - Filter parameters: `is_published` (Blog), `status`/`stage` (CRM)
- **AI-Ready Endpoints** on all example apps:
  - `POST /api/posts/{id}/ai-suggest-tags/` - Keyword-based tag suggestions (Blog)
  - `GET /api/customers/{id}/ai-context/` - Customer context summary (CRM)
  - `GET /api/tenants/{id}/ai-overview/` - Tenant model overview (Multitenant)
  - All endpoints marked with `ai_exposed=True`, `ai_name`, `ai_description`
  - Discoverable at `/ai/tools` for LLM integration
- **New Test Coverage**:
  - Auth module tests (verify_api_key, require_api_key)
  - Pagination settings tests
  - AI endpoint tests

### Changed
- ViewSet tags updated to "Blog API", "CRM API", "Multitenant API"
- STAGE_ORDER and STAGE_PROBABILITIES moved to module level in CRM
- Example ViewSets now use `dependencies` for auth
- UserSerializer returns `.model_dump()` in CRM views

### Documentation
- New "Authentication (v0.5.8)" sections in patterns docs
- New "Pagination & Ordering (v0.5.8)" sections with examples
- New "AI-Ready Endpoints (v0.5.8)" sections with usage examples
- Updated API endpoint tables with new AI endpoints

---

## [0.5.7] — 2026-02-06

### Added
- **Patterns & Example Packs**: Real-world starter templates
- **New Example Apps**:
  - `examples/blog/` - Full blogging backend with Post, Comment, tags, publish action
  - `examples/crm/` - Simple CRM with Customer, Deal, forecast endpoint
  - `examples/multitenant/` - Multi-tenant SaaS example with tenant middleware
- **Template Support for `aksara startproject`**:
  - `aksara startproject myblog --template blog`
  - `aksara startproject mycrm --template crm`
  - `aksara startproject mysaas --template multitenant`
- **New CLI Commands**:
  - `aksara templates list` - List available templates
- **New Documentation**:
  - `docs/patterns/` - Patterns & Recipes section
  - `patterns/blog.md` - Blog tutorial
  - `patterns/crm.md` - CRM patterns
  - `patterns/multitenant.md` - Multi-tenant patterns

### Changed
- Scaffold templates updated to v0.5.7
- `startproject` now supports `--template` option

### Documentation
- New "Patterns & Recipes" section with real-world examples
- Updated CLI help with template options

---

## [0.5.6] — 2026-02-06

### Added
- **Dev Server Banner Upgrade**: Enhanced `aksara dev` output with:
  - Aksara version display
  - Environment (dev/prod) and debug status
  - All relevant URLs: App, Admin, Studio, API, Docs
  - URLs only shown when feature is enabled
- **Welcome Page in Scaffold**: New projects include a welcome page at `/`:
  - Shows Aksara branding and version
  - "Your Aksara project is running 🚀" confirmation
  - Quick links to Admin, Studio, API, Docs, AI Tools
  - Note about how to customize
- **`aksara info` Polish**: Enhanced environment information display:
  - Framework section with version info
  - Environment section (dev/prod, debug, migrations dir)
  - Database section with backend detection and masked URL
  - Features section showing Admin/Studio/AI Mode status

### Changed
- Dev banner now shows version from `aksara.__version__`
- Scaffold templates updated to v0.5.6
- `aksara info` uses cleaner, aligned formatting

### Documentation
- Updated quickstart.md with new dev banner and welcome page
- Added v0.5.6 changelog entry

---

## [0.5.5] — 2026-02-06

### Added
- **Boilerplate Refresh & Starter Project**: Fresh scaffold for new projects
- **Updated `aksara startproject`**:
  - Creates working Post model + API + Admin out-of-the-box
  - Pre-configured for Admin, Studio, AI Mode
  - Includes middleware (Request ID, Logging)
  - AKSARA configuration dict in settings.py
- **New Scaffold Files**:
  - `models.py` - Working Post model with AI metadata
  - `views.py` - PostViewSet with custom actions
  - `serializers.py` - PostSerializer ready to use
  - `admin.py` - Post registered with ModelAdmin
  - `urls.py` - Post routes pre-registered
- **Updated Project Structure**:
  ```
  myproject/
  ├── main.py          # Admin, Studio, AI auto-mounted
  ├── settings.py      # AKSARA config dict
  ├── app/
  │   ├── models.py    # Working Post model
  │   ├── views.py     # PostViewSet
  │   ├── admin.py     # Post admin
  │   └── ...
  ```
- **Zero-Config Experience**:
  - `/admin` - Admin ready (debug mode)
  - `/studio/ui` - Studio dashboard ready
  - `/ai/tools` - Post ViewSet as AI tool
  - `/api/posts` - CRUD API ready

### Changed
- Scaffold pyproject.toml now requires `aksara>=0.5.5`
- README.md in scaffold now shows all available endpoints
- Example app (examples/basic_app) updated to v0.5.5 patterns
- Quickstart docs updated to match new scaffold

### Documentation
- Updated quickstart.md with new project structure
- Updated example app README.md

---

## [0.5.4] — 2026-02-06

### Added
- **Studio ↔ AI Integration**: Connect Studio with AI tools (LLM-agnostic)
- **New Endpoints**:
  - `GET /studio/ai/context` - AI context export (models, routes, tools, checksums)
  - `GET /studio/ai/schemas` - JSON Schemas for AI operations (plan, patch, query, codegen)
  - `GET /studio/ai/prompts` - Prompt templates for external AI tools
- **New Pydantic Models** (v0.5.4):
  - `StudioAiProjectMeta` - Project metadata for AI context
  - `StudioAiModelSummary` - Lightweight model info for AI
  - `StudioAiRouteSummary` - Route info for AI context
  - `StudioAiToolInfo` - Tool descriptions for AI agents
  - `StudioAiContextExport` - Complete AI context bundle
  - `StudioAiSchemas` - JSON schemas container
  - `StudioAiPromptTemplate` - Single prompt template
  - `StudioAiPrompts` - Prompt templates collection
- **Studio UI "AI Helpers" Panel**:
  - AI Context Export - Copy JSON context for AI assistants
  - AI Schemas - Browse/copy schemas for plan, patch, query, codegen
  - Prompt Templates - Pre-built prompts with placeholders
  - Copy buttons with toast notifications
- **New CLI Command**:
  - `aksara studio ai-context` - Export AI context from CLI
  - `--format json|summary` option

### Important
- **LLM-agnostic**: No AI providers bundled or called
- **No secrets exposed**: AI context filters sensitive data
- **Safe by default**: All new endpoints are read-only

---

## [0.5.3] — 2026-02-06

### Added
- **Studio UI (Phase 1: Static Dashboard)**
  - Embedded zero-build, zero-dependency admin dashboard
  - Clean HTML/CSS/Vanilla JS architecture
  - Light and dark theme support
  - Responsive layout (mobile-friendly)
- **Dashboard Sections**:
  - System Overview - Version info, uptime, environment status
  - Models & Schema - Browse models with field types and relations
  - Routes Explorer - All registered endpoints with filtering
  - Migrations - Status, pending count, conflicts
  - Diagnostics - Live monitoring with 5-second auto-refresh
  - API Explorer - Quick endpoint reference
- **New Endpoints**:
  - `GET /studio/ui` - Serves the dashboard HTML
  - `GET /studio/assets/*` - Serves static assets (CSS, JS, icons)
- **New CLI Commands**:
  - `aksara studio open` - Opens dashboard in browser
  - `aksara studio ui-path` - Shows static assets path
- **New Settings**:
  - `studio_ui_enabled` - Enable/disable the UI (default: True)
  - `studio_ui_auto_open` - Auto-open on server start (future)
  - `studio_ui_title` - Customizable UI title

### Changed
- Version bump from 0.5.2 to 0.5.3
- `aksara studio url` now includes dashboard URL
- Static assets bundled with package

### Security
- UI respects `studio_allowed_origins` setting
- UI disabled in production by default (requires `studio_expose_in_production`)
- Directory traversal protection on assets endpoint

---

## [0.5.2] — 2026-02-15


### Added
- **Runtime Diagnostics Endpoints**: Real-time server introspection
  - `GET /studio/runtime/info` - Process info, uptime, database status, pending migrations
  - `GET /studio/runtime/routes` - Complete route listing with metadata (studio/admin/ai flags)
- **New Pydantic Models**:
  - `StudioRuntimeInfo` - Runtime diagnostics (version, python, debug, env, pid, uptime, etc.)
  - `StudioRouteInfo` - Route metadata (path, methods, name, app_label, is_studio, is_admin, is_ai)
- **Enhanced `aksara dev` Command**:
  - Beautiful startup banner showing App name, URL, Studio URL, Docs URL
  - `--log-level` option (default: info)
  - Clean shutdown message on Ctrl+C
- **Smarter `aksara shell`**:
  - `aquery(Model, **filters)` - Async query helper for quick lookups
  - `run()` - Alias for `arun()` (simpler)
  - Auto-imports app and settings
  - Improved banner showing preloaded objects

### Changed
- Version bump from 0.5.1 to 0.5.2
- Shell now automatically connects to database from settings

---

## [0.5.1] — 2026-02-10

### Added
- **Studio Core Polish**: Richer summaries and security improvements
- **New Endpoints**:
  - `GET /studio/migrations/summary` - Per-app migration statistics with conflict detection
  - `GET /studio/schema/handshake` - JSON Schema for StudioHandshake model (TypeScript generation)
- **Enhanced Context Summary**: 
  - `app_count` - Number of installed/configured apps
  - `database_status` - Live database connection status
  - `migration_status` - Quick migration health overview
  - `schema_checksum` - Convenience property accessor
- **New Pydantic Models**:
  - `StudioMigrationStatus` - Migration health summary
  - `StudioAppMigrationSummary` - Per-app migration stats
  - `StudioMigrationConflict` - Conflict details
  - `StudioMigrationSummary` - Complete migration summary response
- **Origin-based Security**: 
  - Request `Origin` header validation against `studio_allowed_origins`
  - Wildcard (`*`) support for development
  - Missing origin allowed for same-origin/CLI requests

### Security
- Studio endpoints now validate incoming `Origin` header
- Requests from non-allowed origins receive 403 Forbidden
- Clear separation between development and production security

### Changed
- Improved migration discovery to include Python migrations (not just .sql)
- Studio router now applies origin check dependency to all endpoints

---

## [0.5.0] — 2026-02-01

### Added
- **Studio Core & Handshake**: Complete IDE integration foundation
- **Studio Endpoints**:
  - `GET /studio/handshake` - Complete project handshake for Studio IDE
  - `GET /studio/context/summary` - Lightweight schema summary
  - `GET /studio/health` - Health check with database status
- **Studio CLI Commands**:
  - `aksara studio handshake` - Test handshake locally
  - `aksara studio url` - Show Studio endpoint URLs
- **Studio Settings**:
  - `enable_studio` - Enable/disable Studio endpoints (default: True)
  - `studio_expose_in_production` - Allow Studio in non-debug mode
  - `studio_allowed_origins` - CORS origins for Studio access
- Pydantic models for Studio responses:
  - `StudioHandshake`, `StudioCapability`, `StudioDatabaseStatus`
  - `StudioProjectInfo`, `StudioChecksums`, `StudioContextSummary`
  - `StudioHealthResponse`, `StudioModelSummary`
- Checksum utilities for cache invalidation
- Comprehensive Studio documentation in `docs/docs/studio/`
- 21 new Studio unit tests

### Changed
- Version bump from 0.4.11 to 0.5.0
- Studio endpoints automatically enabled in debug mode
- AI registry setup now also mounts Studio router

### Security
- Studio endpoints disabled in production by default
- Requires explicit `studio_expose_in_production=True` to enable in production

---

## [0.4.11] — 2026-01-31

### Added
- **Admin UI/UX Overhaul**: Modern, responsive admin interface
- **JSONAdminWidget**: Interactive JSON editor with syntax highlighting
- **ArrayAdminWidget**: Dynamic list editor for array fields
- **Array Field**: Native PostgreSQL array support (`TEXT[]`, `INTEGER[]`, etc.)
- Auto-detection of JSON and Array fields for widget assignment
- Dark mode support in admin interface
- Mobile-responsive admin sidebar

### Changed
- Redesigned admin templates with modern CSS
- Improved admin navigation with collapsible sidebar
- Enhanced form field rendering with specialized widgets

### Fixed
- Template syntax errors in admin base template
- Widget render method signature consistency
- Admin URL generation for model list views

---

## [0.4.10] — 2026-01-20

### Added
- Aksara rename release (formerly Vidyut)
- Updated all package references and imports

### Changed
- Package name from `vidyut` to `aksara`
- CLI command from `vidyut` to `aksara`
- All internal module references updated

---

## [0.4.9] — 2025-01-14

### Fixed
- Version alignment across `__init__.py`, `pyproject.toml`, and documentation
- Test stability improvements across all 2015 tests
- Admin permission checks for model access
- Migration executor edge cases

### Changed
- Improved error messages for validation failures
- Enhanced debug page AI suggestions
- Better query profiling output format

### Documentation
- Complete documentation rewrite with MkDocs + Material
- Added comprehensive tutorials
- Added AI Mode documentation

---

## [0.4.8] — 2025-01-10

### Added
- AI Mode: Schema Doctor for automated schema analysis
- AI Mode: Patch Engine for safe code modifications
- Multi-app autodiscovery improvements

### Fixed
- M2M relationship expansion batching
- Query capture in debug mode
- Tenant middleware context propagation

---

## [0.4.7] — 2025-01-05

### Added
- AI Mode: Agent Runtime for executing AI agents
- AI Mode: Planner for multi-step task planning
- CLI `ai agent` and `ai plan` commands

### Fixed
- Select related with nested prefetch
- Admin site registration ordering
- Logging middleware request body handling

---

## [0.4.6] — 2024-12-28

### Added
- AI Mode: Codegen for generating models, viewsets, serializers
- AI Mode: Context Engine for gathering code context
- CLI `ai generate` command

### Changed
- Improved migration conflict detection
- Better error pages in debug mode

### Fixed
- ForeignKey on_delete behavior
- Serializer validation ordering

---

## [0.4.5] — 2024-12-20

### Added
- AI Mode: Query Engine for natural language queries
- CLI `ai query` command
- AI debug tab in error pages

### Changed
- Enhanced admin interface styling
- Improved ViewSet action routing

### Fixed
- Pagination with complex filters
- Request ID middleware propagation

---

## [0.4.4] — 2024-12-15

### Added
- Basic AI Mode infrastructure
- AI configuration settings
- OpenAI and Anthropic provider support

### Changed
- Refactored middleware stack
- Improved settings validation

---

## [0.4.3] — 2024-12-10

### Added
- Admin interface with ModelAdmin
- Admin permissions system
- Admin site customization

### Fixed
- Model Meta inheritance
- Many-to-many through models

---

## [0.4.2] — 2024-12-05

### Added
- Request ID middleware
- Tenant middleware
- Logging middleware with JSON format

### Changed
- Middleware execution order
- Request object attributes

---

## [0.4.1] — 2024-12-01

### Added
- Debug error pages with context
- Query profiling tools
- Development toolbar

### Fixed
- Hot reload in development
- Static file serving

---

## [0.4.0] — 2024-11-25

### Added
- Complete API framework
- ModelViewSet with full CRUD
- Custom actions with @action decorator
- Serializers with validation
- Permission classes
- Authentication backends
- Pagination classes
- Filtering and search

### Changed
- Major API redesign
- New routing system
- Improved type hints

### Breaking Changes
- ViewSet API changed
- Serializer API changed
- Router registration changed

---

## [0.3.0] — 2024-10-15

### Added
- Migration system
- Migration operations
- Migration executor
- CLI migration commands

### Changed
- Model field definitions
- Database schema generation

---

## [0.2.0] — 2024-09-01

### Added
- Full ORM implementation
- All field types
- QuerySet API
- Relationships (FK, M2M)
- Manager customization

### Changed
- Model base class
- Field descriptor protocol

---

## [0.1.0] — 2024-07-15

### Added
- Initial release
- Basic Model class
- Core field types
- Simple queries
- CLI scaffolding
- Project structure

---

## Version Numbering

Aksara follows [Semantic Versioning](https://semver.org/):

- **MAJOR**: Breaking changes
- **MINOR**: New features (backwards compatible)
- **PATCH**: Bug fixes (backwards compatible)

---

## Upgrade Guides

### 0.3.x → 0.4.x

1. Update ViewSet imports:
```python
# Old
from aksara.views import ViewSet

# New
from aksara.api import ViewSet, ModelViewSet
```

2. Update serializer definitions:
```python
# Old
class UserSerializer(Serializer):
    class Meta:
        model = User

# New
class UserSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "name"]
```

3. Update router registration:
```python
# Old
router.add_route("/users", UserViewSet)

# New
router.register("users", UserViewSet)
```

### 0.2.x → 0.3.x

1. Create initial migration:
```bash
aksara makemigrations --initial
```

2. Apply migrations:
```bash
aksara migrate
```

---

## Links

- [GitHub Releases](https://github.com/aksara/aksara/releases)
- [Roadmap](roadmap.md)
- [Migration Guides](getting-started/index.md)
