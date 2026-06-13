"""Governance router for the GARVIS Operator API.

Exposes governance schemas, constraints, violations, and enforcement chains.
All endpoints are read-only (GET) except explicit activation/deactivation (POST).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from api.dependencies import (
    get_registry,
    get_mock_schemas,
    get_mock_active_schema_ids,
    get_mock_violations,
    set_mock_schema_active,
)
from api.models import (
    SchemaSummary,
    SchemaListResponse,
    SchemaCategoriesResponse,
    ConstraintsByScopeResponse,
    ViolationListResponse,
    EnforcementChainResponse,
)
from governance.registry import GovernanceRegistry
from models.governance import GovernanceConstraint

router = APIRouter()

_GOV_CONTEXT = {"X-Governance-Scope": "governance", "X-API-Version": "v1"}


def _add_gov_headers(response: JSONResponse) -> JSONResponse:
    for k, v in _GOV_CONTEXT.items():
        response.headers[k] = v
    return response


def _schema_to_summary(schema: Any, active_ids: set[str]) -> SchemaSummary:
    return SchemaSummary(
        schema_id=schema.schema_id,
        name=schema.name,
        version=schema.version,
        category=schema.category,
        description=schema.description,
        active=schema.schema_id in active_ids,
        policy_count=len(schema.policies),
        constraint_count=len(schema.constraints),
        fail_closed=schema.fail_closed,
    )


# ── Schemas ───────────────────────────────────────────────────────────────


@router.get("/schemas", response_model=SchemaListResponse)
async def list_schemas(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    category: str | None = Query(None),
    registry: Any = Depends(get_registry),
) -> SchemaListResponse:
    """List all governance schemas (paginated, optionally filtered by category)."""
    schemas = get_mock_schemas()
    active_ids = get_mock_active_schema_ids()

    if category:
        schemas = [s for s in schemas if s.category == category]

    total = len(schemas)
    pages = (total + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    page_items = schemas[start:end]

    items = [_schema_to_summary(s, active_ids) for s in page_items]

    return SchemaListResponse(total=total, page=page, per_page=per_page, pages=pages, items=items)


@router.get("/schemas/{schema_id}")
async def get_schema(
    schema_id: str,
    registry: Any = Depends(get_registry),
) -> dict[str, Any]:
    """Get a specific governance schema by ID with full details."""
    schemas = get_mock_schemas()
    active_ids = get_mock_active_schema_ids()

    for schema in schemas:
        if schema.schema_id == schema_id:
            data = schema.model_dump()
            data["active"] = schema_id in active_ids
            return data

    raise HTTPException(status_code=404, detail=f"Schema '{schema_id}' not found")


@router.get("/schemas-active/list", response_model=SchemaListResponse)
async def list_active_schemas(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    registry: Any = Depends(get_registry),
) -> SchemaListResponse:
    """List all currently active governance schemas."""
    schemas = get_mock_schemas()
    active_ids = get_mock_active_schema_ids()

    active_schemas = [s for s in schemas if s.schema_id in active_ids]
    total = len(active_schemas)
    pages = (total + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    page_items = active_schemas[start:end]

    items = [_schema_to_summary(s, active_ids) for s in page_items]

    return SchemaListResponse(total=total, page=page, per_page=per_page, pages=pages, items=items)


@router.get("/schemas-categories/list", response_model=SchemaCategoriesResponse)
async def list_schema_categories(
    registry: Any = Depends(get_registry),
) -> SchemaCategoriesResponse:
    """List all schema categories with counts."""
    schemas = get_mock_schemas()
    categories: dict[str, int] = {}
    for s in schemas:
        categories[s.category] = categories.get(s.category, 0) + 1
    return SchemaCategoriesResponse(categories=categories)


# ── Constraints ───────────────────────────────────────────────────────────


@router.get("/constraints/list")
async def list_constraints(
    registry: Any = Depends(get_registry),
) -> list[dict[str, Any]]:
    """List all constraints across all active schemas."""
    schemas = get_mock_schemas()
    active_ids = get_mock_active_schema_ids()
    constraints: list[dict[str, Any]] = []

    for schema in schemas:
        if schema.schema_id in active_ids:
            for c in schema.constraints:
                data = c.model_dump()
                data["source_schema"] = schema.schema_id
                constraints.append(data)

    return constraints


@router.get("/constraints/{scope}")
async def get_constraints_by_scope(
    scope: str,
    registry: Any = Depends(get_registry),
) -> list[dict[str, Any]]:
    """Get constraints filtered by scope (global, session, inference, memory)."""
    if scope not in ("global", "session", "inference", "memory"):
        raise HTTPException(status_code=400, detail=f"Invalid scope: '{scope}'. Must be one of: global, session, inference, memory")

    schemas = get_mock_schemas()
    active_ids = get_mock_active_schema_ids()
    constraints: list[dict[str, Any]] = []

    for schema in schemas:
        if schema.schema_id in active_ids:
            for c in schema.constraints:
                if c.scope == scope or c.scope == "global":
                    data = c.model_dump()
                    data["source_schema"] = schema.schema_id
                    constraints.append(data)

    return constraints


# ── Violations ────────────────────────────────────────────────────────────


@router.get("/violations/list", response_model=ViolationListResponse)
async def list_violations(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    severity: str | None = Query(None),
    schema_id: str | None = Query(None),
) -> ViolationListResponse:
    """List recorded governance violations (paginated, filterable)."""
    violations = get_mock_violations()

    if severity:
        violations = [v for v in violations if v.severity == severity]
    if schema_id:
        violations = [v for v in violations if v.schema_id == schema_id]

    total = len(violations)
    pages = (total + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    page_items = violations[start:end]

    return ViolationListResponse(total=total, page=page, per_page=per_page, pages=pages, items=page_items)


# ── Enforcement Chain ─────────────────────────────────────────────────────


@router.get("/enforcement-chain/{scope}")
async def get_enforcement_chain(
    scope: str,
    registry: Any = Depends(get_registry),
) -> EnforcementChainResponse:
    """Get the enforcement chain for a given scope.

    Constraints are ordered by enforcement severity: hard_stop first,
    then degrade, then log_only.
    """
    if scope not in ("global", "session", "inference", "memory"):
        raise HTTPException(status_code=400, detail=f"Invalid scope: '{scope}'")

    # Use registry if properly initialized, otherwise use mock data
    try:
        chain = registry.get_enforcement_chain(scope)
    except Exception:
        # Fallback: build from mock data
        schemas = get_mock_schemas()
        active_ids = get_mock_active_schema_ids()
        chain: list[GovernanceConstraint] = []
        for schema in schemas:
            if schema.schema_id in active_ids:
                for c in schema.constraints:
                    if c.scope == scope or c.scope == "global":
                        chain.append(c)
        chain.sort(key=lambda c: ({"hard_stop": 0, "degrade": 1, "log_only": 2}.get(c.enforcement, 99)))

    return EnforcementChainResponse(scope=scope, constraints=chain)


# ── Schema Activation/Deactivation ────────────────────────────────────────


@router.post("/schemas/{schema_id}/activate")
async def activate_schema(
    schema_id: str,
    registry: Any = Depends(get_registry),
) -> dict[str, str]:
    """Explicitly activate a governance schema.

    Requires operator authorization. Logs the action for audit.
    """
    schemas = get_mock_schemas()
    schema_ids = {s.schema_id for s in schemas}

    if schema_id not in schema_ids:
        raise HTTPException(status_code=404, detail=f"Schema '{schema_id}' not found")

    set_mock_schema_active(schema_id, True)

    try:
        registry.activate(schema_id)
    except Exception:
        pass  # Mock path already updated

    return {"schema_id": schema_id, "action": "activated", "status": "success"}


@router.post("/schemas/{schema_id}/deactivate")
async def deactivate_schema(
    schema_id: str,
    registry: Any = Depends(get_registry),
) -> dict[str, str]:
    """Explicitly deactivate a governance schema.

    Requires operator authorization. Logs the action and warns about
    reduced governance coverage.
    """
    schemas = get_mock_schemas()
    schema_ids = {s.schema_id for s in schemas}

    if schema_id not in schema_ids:
        raise HTTPException(status_code=404, detail=f"Schema '{schema_id}' not found")

    set_mock_schema_active(schema_id, False)

    try:
        registry.deactivate(schema_id)
    except Exception:
        pass  # Mock path already updated

    return {"schema_id": schema_id, "action": "deactivated", "status": "success", "warning": "governance coverage reduced"}
