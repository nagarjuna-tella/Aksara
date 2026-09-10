"""
Aksara Security Matrix Loader and Validator

Loads and validates security/security_matrix.yml, which is the canonical
inventory of Aksara's generated surfaces, actors, risks, and adversarial
scenarios.

Round 1: baseline inventory and validation only.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Default matrix path discovery
# ---------------------------------------------------------------------------

_MATRIX_FILENAME = "security_matrix.yml"
_MATRIX_EXAMPLE_FILENAME = "security_matrix.example.yml"
_MATRIX_SEARCH_DIRS = [
    "security",   # <repo_root>/security/security_matrix.yml
    ".",           # <repo_root>/security_matrix.yml
]


def _matrix_search_roots() -> list:
    search_roots = [Path.cwd()]
    here = Path(__file__).resolve().parent
    for parent in [here.parent.parent, here.parent.parent.parent]:
        if parent not in search_roots:
            search_roots.append(parent)
    return search_roots


def _find_default_matrix_path() -> Optional[Path]:
    """Search for security_matrix.yml relative to the project root."""
    configured_path = os.environ.get("AKSARA_SECURITY_MATRIX_PATH")
    if configured_path:
        candidate = Path(configured_path).expanduser()
        if candidate.exists():
            return candidate
        return None

    for root in _matrix_search_roots():
        for subdir in _MATRIX_SEARCH_DIRS:
            candidate = root / subdir / _MATRIX_FILENAME
            if candidate.exists():
                return candidate
    return None


def _find_example_matrix_path() -> Optional[Path]:
    """Search for security_matrix.example.yml relative to the project root."""
    for root in _matrix_search_roots():
        for subdir in _MATRIX_SEARCH_DIRS:
            candidate = root / subdir / _MATRIX_EXAMPLE_FILENAME
            if candidate.exists():
                return candidate
    return None


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

VALID_SEVERITIES = {"low", "medium", "high", "critical"}
VALID_EXPECTED = {"allow", "deny", "warn", "block", "warn_or_block"}
VALID_STATUSES = {"covered", "partial", "planned", "not_applicable"}


@dataclass
class MatrixSurface:
    id: str
    name: str
    category: str
    implemented: Any  # bool or "unknown"
    description: str


@dataclass
class MatrixActor:
    id: str
    description: str


@dataclass
class MatrixRisk:
    id: str
    severity: str
    description: str


@dataclass
class MatrixScenario:
    id: str
    surface: str
    actor: str
    risk: str
    expected: str
    status: str
    description: str


@dataclass
class MatrixMetadata:
    name: str
    description: str
    owner: str
    status: str
    round: int
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SecurityMatrix:
    version: int
    metadata: MatrixMetadata
    surfaces: List[MatrixSurface]
    actors: List[MatrixActor]
    risks: List[MatrixRisk]
    scenarios: List[MatrixScenario]


@dataclass
class MatrixValidationIssue:
    field: str
    message: str
    severity: str = "error"  # "error" or "warning"


# ---------------------------------------------------------------------------
# YAML loader
# ---------------------------------------------------------------------------

def _load_yaml(path: Path) -> Dict[str, Any]:
    """Load a YAML file, falling back to a clear error if PyYAML is absent."""
    try:
        import yaml  # type: ignore[import]
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if not isinstance(data, dict):
            raise ValueError(f"Expected a YAML mapping at top level, got {type(data).__name__}")
        return data
    except ImportError:
        raise ImportError(
            "PyYAML is required to load security_matrix.yml. "
            "Install it: pip install pyyaml"
        )


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

def validate_security_matrix(matrix: Dict[str, Any]) -> List[MatrixValidationIssue]:
    """
    Validate a parsed matrix dict.

    Returns a list of MatrixValidationIssue. Empty list means valid.
    """
    issues: List[MatrixValidationIssue] = []

    # Top-level keys
    for key in ("version", "metadata", "surfaces", "actors", "risks", "scenarios"):
        if key not in matrix:
            issues.append(MatrixValidationIssue(
                field=key,
                message=f"Required top-level key '{key}' is missing.",
            ))

    if issues:
        return issues  # Cannot continue without structure

    # version
    if not isinstance(matrix.get("version"), int):
        issues.append(MatrixValidationIssue(field="version", message="'version' must be an integer."))

    # metadata
    meta = matrix.get("metadata", {})
    if not isinstance(meta, dict):
        issues.append(MatrixValidationIssue(field="metadata", message="'metadata' must be a mapping."))
    else:
        for mkey in ("name", "description", "owner", "status"):
            if not meta.get(mkey):
                issues.append(MatrixValidationIssue(
                    field=f"metadata.{mkey}",
                    message=f"metadata.{mkey} is missing or empty.",
                ))

    # surfaces
    surfaces_raw = matrix.get("surfaces", [])
    if not isinstance(surfaces_raw, list):
        issues.append(MatrixValidationIssue(field="surfaces", message="'surfaces' must be a list."))
        surfaces_raw = []

    surface_ids: set[str] = set()
    for i, s in enumerate(surfaces_raw):
        if not isinstance(s, dict):
            issues.append(MatrixValidationIssue(field=f"surfaces[{i}]", message="Each surface must be a mapping."))
            continue
        for req in ("id", "name", "category", "implemented", "description"):
            if req not in s:
                issues.append(MatrixValidationIssue(
                    field=f"surfaces[{i}].{req}",
                    message=f"Surface at index {i} is missing required field '{req}'.",
                ))
        sid = s.get("id", "")
        if sid:
            if sid in surface_ids:
                issues.append(MatrixValidationIssue(
                    field=f"surfaces.id",
                    message=f"Duplicate surface id: '{sid}'.",
                ))
            surface_ids.add(sid)

    # actors
    actors_raw = matrix.get("actors", [])
    if not isinstance(actors_raw, list):
        issues.append(MatrixValidationIssue(field="actors", message="'actors' must be a list."))
        actors_raw = []

    actor_ids: set[str] = set()
    for i, a in enumerate(actors_raw):
        if not isinstance(a, dict):
            issues.append(MatrixValidationIssue(field=f"actors[{i}]", message="Each actor must be a mapping."))
            continue
        for req in ("id", "description"):
            if req not in a:
                issues.append(MatrixValidationIssue(
                    field=f"actors[{i}].{req}",
                    message=f"Actor at index {i} is missing required field '{req}'.",
                ))
        aid = a.get("id", "")
        if aid:
            if aid in actor_ids:
                issues.append(MatrixValidationIssue(
                    field="actors.id",
                    message=f"Duplicate actor id: '{aid}'.",
                ))
            actor_ids.add(aid)

    # risks
    risks_raw = matrix.get("risks", [])
    if not isinstance(risks_raw, list):
        issues.append(MatrixValidationIssue(field="risks", message="'risks' must be a list."))
        risks_raw = []

    risk_ids: set[str] = set()
    for i, r in enumerate(risks_raw):
        if not isinstance(r, dict):
            issues.append(MatrixValidationIssue(field=f"risks[{i}]", message="Each risk must be a mapping."))
            continue
        for req in ("id", "severity", "description"):
            if req not in r:
                issues.append(MatrixValidationIssue(
                    field=f"risks[{i}].{req}",
                    message=f"Risk at index {i} is missing required field '{req}'.",
                ))
        rid = r.get("id", "")
        if rid:
            if rid in risk_ids:
                issues.append(MatrixValidationIssue(
                    field="risks.id",
                    message=f"Duplicate risk id: '{rid}'.",
                ))
            risk_ids.add(rid)
        sev = r.get("severity", "")
        if sev and sev not in VALID_SEVERITIES:
            issues.append(MatrixValidationIssue(
                field=f"risks[{i}].severity",
                message=f"Invalid severity '{sev}'. Must be one of: {sorted(VALID_SEVERITIES)}.",
            ))

    # scenarios
    scenarios_raw = matrix.get("scenarios", [])
    if not isinstance(scenarios_raw, list):
        issues.append(MatrixValidationIssue(field="scenarios", message="'scenarios' must be a list."))
        scenarios_raw = []

    scenario_ids: set[str] = set()
    for i, sc in enumerate(scenarios_raw):
        if not isinstance(sc, dict):
            issues.append(MatrixValidationIssue(field=f"scenarios[{i}]", message="Each scenario must be a mapping."))
            continue
        for req in ("id", "surface", "actor", "risk", "expected", "status", "description"):
            if req not in sc:
                issues.append(MatrixValidationIssue(
                    field=f"scenarios[{i}].{req}",
                    message=f"Scenario at index {i} is missing required field '{req}'.",
                ))
        scid = sc.get("id", "")
        if scid:
            if scid in scenario_ids:
                issues.append(MatrixValidationIssue(
                    field="scenarios.id",
                    message=f"Duplicate scenario id: '{scid}'.",
                ))
            scenario_ids.add(scid)

        # Cross-reference checks
        s_ref = sc.get("surface", "")
        if s_ref and s_ref not in surface_ids:
            issues.append(MatrixValidationIssue(
                field=f"scenarios[{i}].surface",
                message=f"Scenario '{scid}' references unknown surface '{s_ref}'.",
            ))
        a_ref = sc.get("actor", "")
        if a_ref and a_ref not in actor_ids:
            issues.append(MatrixValidationIssue(
                field=f"scenarios[{i}].actor",
                message=f"Scenario '{scid}' references unknown actor '{a_ref}'.",
            ))
        r_ref = sc.get("risk", "")
        if r_ref and r_ref not in risk_ids:
            issues.append(MatrixValidationIssue(
                field=f"scenarios[{i}].risk",
                message=f"Scenario '{scid}' references unknown risk '{r_ref}'.",
            ))
        exp = sc.get("expected", "")
        if exp and exp not in VALID_EXPECTED:
            issues.append(MatrixValidationIssue(
                field=f"scenarios[{i}].expected",
                message=f"Invalid expected value '{exp}'. Must be one of: {sorted(VALID_EXPECTED)}.",
            ))
        st = sc.get("status", "")
        if st and st not in VALID_STATUSES:
            issues.append(MatrixValidationIssue(
                field=f"scenarios[{i}].status",
                message=f"Invalid status '{st}'. Must be one of: {sorted(VALID_STATUSES)}.",
            ))

    return issues


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_security_matrix(path: Optional[str | Path] = None) -> SecurityMatrix:
    """
    Load and parse the security matrix YAML file.

    Args:
        path: Explicit path to security_matrix.yml. If None, searches for
              it in <cwd>/security/ or <repo_root>/security/.

    Returns:
        SecurityMatrix dataclass instance.

    Raises:
        FileNotFoundError: If the matrix file cannot be found.
        ValueError: If the matrix fails validation.
        ImportError: If PyYAML is not installed.
    """
    if path is None:
        found = _find_default_matrix_path()
        if found is None:
            raise FileNotFoundError(
                f"Could not find {_MATRIX_FILENAME}. "
                "Expected at security/security_matrix.yml relative to the project root. "
                "Run 'aksara doctor security-check' for guidance."
            )
        resolved = found
    else:
        resolved = Path(path)
        if not resolved.exists():
            raise FileNotFoundError(f"Security matrix file not found: {resolved}")

    data = _load_yaml(resolved)

    issues = validate_security_matrix(data)
    errors = [i for i in issues if i.severity == "error"]
    if errors:
        msgs = "\n".join(f"  - [{i.field}] {i.message}" for i in errors)
        raise ValueError(f"security_matrix.yml validation failed:\n{msgs}")

    meta_raw = data.get("metadata", {})
    metadata = MatrixMetadata(
        name=meta_raw.get("name", ""),
        description=str(meta_raw.get("description", "")),
        owner=meta_raw.get("owner", ""),
        status=meta_raw.get("status", ""),
        round=int(meta_raw.get("round", 0)),
        raw=meta_raw,
    )

    surfaces = [
        MatrixSurface(
            id=s["id"],
            name=s["name"],
            category=s["category"],
            implemented=s["implemented"],
            description=str(s.get("description", "")),
        )
        for s in data.get("surfaces", [])
    ]
    actors = [
        MatrixActor(id=a["id"], description=str(a.get("description", "")))
        for a in data.get("actors", [])
    ]
    risks = [
        MatrixRisk(id=r["id"], severity=r["severity"], description=str(r.get("description", "")))
        for r in data.get("risks", [])
    ]
    scenarios = [
        MatrixScenario(
            id=sc["id"],
            surface=sc["surface"],
            actor=sc["actor"],
            risk=sc["risk"],
            expected=sc["expected"],
            status=sc["status"],
            description=str(sc.get("description", "")),
        )
        for sc in data.get("scenarios", [])
    ]

    return SecurityMatrix(
        version=int(data.get("version", 1)),
        metadata=metadata,
        surfaces=surfaces,
        actors=actors,
        risks=risks,
        scenarios=scenarios,
    )
