# Changelog

All notable changes to Vidyut.

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

Vidyut follows [Semantic Versioning](https://semver.org/):

- **MAJOR**: Breaking changes
- **MINOR**: New features (backwards compatible)
- **PATCH**: Bug fixes (backwards compatible)

---

## Upgrade Guides

### 0.3.x → 0.4.x

1. Update ViewSet imports:
```python
# Old
from vidyut.views import ViewSet

# New
from vidyut.api import ViewSet, ModelViewSet
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
vidyut makemigrations --initial
```

2. Apply migrations:
```bash
vidyut migrate
```

---

## Links

- [GitHub Releases](https://github.com/vidyut/vidyut/releases)
- [Roadmap](roadmap.md)
- [Migration Guides](getting-started/index.md)
