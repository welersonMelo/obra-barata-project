"""PostgreSQL repository for users and persisted projects."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from psycopg.types.json import Jsonb

from app.database import get_connection
from app.models.projects import ProjectCreate, ProjectResponse


class ProjectNotFoundError(RuntimeError):
    """Raised when a project does not exist for the test user."""


def _json_payload(value: Any) -> Jsonb | None:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return Jsonb(value)


def _iso(value: datetime | str) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _project_from_row(row: dict[str, Any]) -> ProjectResponse:
    return ProjectResponse(
        id=str(row["id"]),
        name=row["name"],
        type=row["project_type"],
        address=row["address"],
        areaBuilt=row["area_built"],
        finishProfile=row["finish_profile"],
        status=row["status"],
        createdAt=_iso(row["created_at"]),
        updatedAt=_iso(row["updated_at"]),
        upload=row["upload"],
        materialList=row["material_list"],
        pricedList=row["priced_list"],
        removedMaterialIds=row["removed_material_ids"] or [],
    )


class ProjectRepository:
    """Persist and read project state from PostgreSQL."""

    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        with get_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, username, password_hash FROM app_users WHERE username = %s",
                (username,),
            )
            return cursor.fetchone()

    def list_projects(self, user_id: str) -> list[ProjectResponse]:
        with get_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM projects
                WHERE user_id = %s
                ORDER BY updated_at DESC
                """,
                (user_id,),
            )
            return [_project_from_row(row) for row in cursor.fetchall()]

    def get_project(self, user_id: str, project_id: str) -> ProjectResponse:
        with get_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM projects WHERE user_id = %s AND id = %s",
                (user_id, project_id),
            )
            row = cursor.fetchone()
            if row is None:
                raise ProjectNotFoundError("Projeto nao encontrado.")
            return _project_from_row(row)

    def create_project(self, user_id: str, payload: ProjectCreate) -> ProjectResponse:
        project_id = str(uuid4())
        with get_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO projects (
                    id,
                    user_id,
                    name,
                    project_type,
                    address,
                    area_built,
                    finish_profile,
                    status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'rascunho')
                RETURNING *
                """,
                (
                    project_id,
                    user_id,
                    payload.name.strip(),
                    payload.type.strip() or "Residencial",
                    payload.address.strip(),
                    payload.areaBuilt.strip(),
                    payload.finishProfile,
                ),
            )
            row = cursor.fetchone()
            connection.commit()
            return _project_from_row(row)

    def update_project(
        self,
        user_id: str,
        project_id: str,
        updates: dict[str, Any],
    ) -> ProjectResponse:
        if not updates:
            return self.get_project(user_id=user_id, project_id=project_id)

        field_map = {
            "name": ("name", lambda value: value.strip()),
            "type": ("project_type", lambda value: value.strip() or "Residencial"),
            "address": ("address", lambda value: value.strip()),
            "areaBuilt": ("area_built", lambda value: value.strip()),
            "finishProfile": ("finish_profile", str),
            "status": ("status", str),
            "upload": ("upload", _json_payload),
            "materialList": ("material_list", _json_payload),
            "pricedList": ("priced_list", _json_payload),
            "removedMaterialIds": ("removed_material_ids", _json_payload),
        }
        assignments = []
        values = []
        for field_name, value in updates.items():
            if field_name not in field_map:
                continue
            if field_name == "removedMaterialIds" and value is None:
                value = []
            column_name, coerce = field_map[field_name]
            assignments.append(f"{column_name} = %s")
            values.append(coerce(value) if value is not None else None)

        if not assignments:
            return self.get_project(user_id=user_id, project_id=project_id)

        assignments.append("updated_at = now()")
        values.extend([user_id, project_id])
        with get_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE projects
                SET {", ".join(assignments)}
                WHERE user_id = %s AND id = %s
                RETURNING *
                """,
                values,
            )
            row = cursor.fetchone()
            if row is None:
                raise ProjectNotFoundError("Projeto nao encontrado.")
            connection.commit()
            return _project_from_row(row)
