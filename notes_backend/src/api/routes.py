from __future__ import annotations

from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.api.schemas import (
    NoteCreate,
    NoteOut,
    NoteUpdate,
    NotesListResponse,
    Tag,
    TagsListResponse,
)


def _row_to_tag(row) -> Tag:
    return Tag(id=row["id"], name=row["name"])


def _fetch_note_tags(conn, note_id: UUID) -> List[Tag]:
    rows = conn.execute(
        text(
            """
            SELECT t.id, t.name
            FROM tags t
            JOIN note_tags nt ON nt.tag_id = t.id
            WHERE nt.note_id = :note_id
            ORDER BY t.name ASC
            """
        ),
        {"note_id": str(note_id)},
    ).mappings().all()
    return [_row_to_tag(r) for r in rows]


def _ensure_tags(conn, tag_names: List[str]) -> List[Tag]:
    clean = []
    for n in tag_names:
        n2 = (n or "").strip()
        if not n2:
            continue
        if len(n2) > 64:
            raise HTTPException(status_code=400, detail=f"Tag too long: {n2}")
        clean.append(n2.lower())

    unique = sorted(set(clean))
    tags: List[Tag] = []
    for name in unique:
        row = conn.execute(
            text("SELECT id, name FROM tags WHERE name = :name"),
            {"name": name},
        ).mappings().first()
        if row:
            tags.append(_row_to_tag(row))
            continue

        new_id = uuid4()
        conn.execute(
            text("INSERT INTO tags (id, name) VALUES (:id, :name)"),
            {"id": str(new_id), "name": name},
        )
        tags.append(Tag(id=new_id, name=name))

    return tags


def _set_note_tags(conn, note_id: UUID, tag_names: List[str]) -> List[Tag]:
    tags = _ensure_tags(conn, tag_names)
    conn.execute(text("DELETE FROM note_tags WHERE note_id = :note_id"), {"note_id": str(note_id)})
    for t in tags:
        conn.execute(
            text(
                "INSERT INTO note_tags (note_id, tag_id) VALUES (:note_id, :tag_id) ON CONFLICT DO NOTHING"
            ),
            {"note_id": str(note_id), "tag_id": str(t.id)},
        )
    return tags


# PUBLIC_INTERFACE
def build_router(engine: Engine) -> APIRouter:
    """Build and return the API router for notes + tags routes."""
    router = APIRouter(prefix="/api", tags=["notes"])

    @router.get(
        "/notes",
        response_model=NotesListResponse,
        summary="List notes",
        description="List notes with optional search, tag filtering, and pinned/favorite filters.",
        operation_id="list_notes",
    )
    def list_notes(
        q: Optional[str] = Query(None, description="Search query (title/content)"),
        tag: Optional[str] = Query(None, description="Filter by tag name"),
        pinned: Optional[bool] = Query(None, description="Filter pinned notes"),
        favorite: Optional[bool] = Query(None, description="Filter favorite notes"),
        limit: int = Query(50, ge=1, le=200, description="Page size"),
        offset: int = Query(0, ge=0, description="Offset for pagination"),
    ):
        with engine.begin() as conn:
            where = []
            params = {"limit": limit, "offset": offset}

            if q:
                where.append("(n.title ILIKE :q OR n.content ILIKE :q)")
                params["q"] = f"%{q}%"
            if pinned is not None:
                where.append("n.is_pinned = :pinned")
                params["pinned"] = pinned
            if favorite is not None:
                where.append("n.is_favorite = :favorite")
                params["favorite"] = favorite
            if tag:
                where.append(
                    """
                    EXISTS (
                        SELECT 1 FROM note_tags nt
                        JOIN tags t ON t.id = nt.tag_id
                        WHERE nt.note_id = n.id AND t.name = :tag
                    )
                    """
                )
                params["tag"] = tag.strip().lower()

            where_sql = ("WHERE " + " AND ".join(where)) if where else ""

            total = conn.execute(
                text(f"SELECT COUNT(*) AS c FROM notes n {where_sql}"),
                params,
            ).mappings().one()["c"]

            rows = conn.execute(
                text(
                    f"""
                    SELECT n.id, n.title, n.is_pinned, n.is_favorite, n.updated_at
                    FROM notes n
                    {where_sql}
                    ORDER BY n.is_pinned DESC, n.updated_at DESC
                    LIMIT :limit OFFSET :offset
                    """
                ),
                params,
            ).mappings().all()

            items = []
            for r in rows:
                tag_rows = conn.execute(
                    text(
                        """
                        SELECT t.name
                        FROM tags t
                        JOIN note_tags nt ON nt.tag_id = t.id
                        WHERE nt.note_id = :note_id
                        ORDER BY t.name ASC
                        """
                    ),
                    {"note_id": str(r["id"])},
                ).mappings().all()
                items.append(
                    {
                        "id": r["id"],
                        "title": r["title"],
                        "is_pinned": r["is_pinned"],
                        "is_favorite": r["is_favorite"],
                        "updated_at": r["updated_at"],
                        "tags": [tr["name"] for tr in tag_rows],
                    }
                )

            return {"items": items, "total": total}

    @router.post(
        "/notes",
        response_model=NoteOut,
        summary="Create note",
        description="Create a new note with optional tags.",
        operation_id="create_note",
    )
    def create_note(payload: NoteCreate):
        with engine.begin() as conn:
            note_id = uuid4()
            conn.execute(
                text(
                    """
                    INSERT INTO notes (id, title, content, content_format, is_pinned, is_favorite)
                    VALUES (:id, :title, :content, :content_format, :is_pinned, :is_favorite)
                    """
                ),
                {
                    "id": str(note_id),
                    "title": payload.title,
                    "content": payload.content,
                    "content_format": payload.content_format,
                    "is_pinned": payload.is_pinned,
                    "is_favorite": payload.is_favorite,
                },
            )
            tags = _set_note_tags(conn, note_id, payload.tags)

            row = conn.execute(
                text("SELECT * FROM notes WHERE id = :id"),
                {"id": str(note_id)},
            ).mappings().one()

            return {
                "id": row["id"],
                "title": row["title"],
                "content": row["content"],
                "content_format": row["content_format"],
                "is_pinned": row["is_pinned"],
                "is_favorite": row["is_favorite"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "tags": tags,
            }

    @router.get(
        "/notes/{note_id}",
        response_model=NoteOut,
        summary="Get note",
        description="Fetch a note by id including tags.",
        operation_id="get_note",
    )
    def get_note(note_id: UUID):
        with engine.begin() as conn:
            row = conn.execute(
                text("SELECT * FROM notes WHERE id = :id"),
                {"id": str(note_id)},
            ).mappings().first()
            if not row:
                raise HTTPException(status_code=404, detail="Note not found")

            tags = _fetch_note_tags(conn, note_id)
            return {
                "id": row["id"],
                "title": row["title"],
                "content": row["content"],
                "content_format": row["content_format"],
                "is_pinned": row["is_pinned"],
                "is_favorite": row["is_favorite"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "tags": tags,
            }

    @router.patch(
        "/notes/{note_id}",
        response_model=NoteOut,
        summary="Update note",
        description="Patch note fields. If tags are provided, they replace existing tags.",
        operation_id="update_note",
    )
    def update_note(note_id: UUID, payload: NoteUpdate):
        with engine.begin() as conn:
            existing = conn.execute(
                text("SELECT * FROM notes WHERE id = :id"),
                {"id": str(note_id)},
            ).mappings().first()
            if not existing:
                raise HTTPException(status_code=404, detail="Note not found")

            fields = {}
            for k in ["title", "content", "content_format", "is_pinned", "is_favorite"]:
                v = getattr(payload, k)
                if v is not None:
                    fields[k] = v

            if fields:
                set_sql = ", ".join([f"{k} = :{k}" for k in fields.keys()])
                conn.execute(
                    text(f"UPDATE notes SET {set_sql} WHERE id = :id"),
                    {"id": str(note_id), **fields},
                )

            if payload.tags is not None:
                tags = _set_note_tags(conn, note_id, payload.tags)
            else:
                tags = _fetch_note_tags(conn, note_id)

            row = conn.execute(
                text("SELECT * FROM notes WHERE id = :id"),
                {"id": str(note_id)},
            ).mappings().one()

            return {
                "id": row["id"],
                "title": row["title"],
                "content": row["content"],
                "content_format": row["content_format"],
                "is_pinned": row["is_pinned"],
                "is_favorite": row["is_favorite"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "tags": tags,
            }

    @router.delete(
        "/notes/{note_id}",
        summary="Delete note",
        description="Delete a note by id.",
        operation_id="delete_note",
        responses={204: {"description": "Deleted"}},
    )
    def delete_note(note_id: UUID):
        with engine.begin() as conn:
            res = conn.execute(
                text("DELETE FROM notes WHERE id = :id"),
                {"id": str(note_id)},
            )
            if res.rowcount == 0:
                raise HTTPException(status_code=404, detail="Note not found")
        return None

    @router.get(
        "/tags",
        response_model=TagsListResponse,
        summary="List tags",
        description="List all tags.",
        operation_id="list_tags",
        tags=["tags"],
    )
    def list_tags():
        with engine.begin() as conn:
            rows = conn.execute(text("SELECT id, name FROM tags ORDER BY name ASC")).mappings().all()
            items = [_row_to_tag(r) for r in rows]
            return {"items": items, "total": len(items)}

    return router
