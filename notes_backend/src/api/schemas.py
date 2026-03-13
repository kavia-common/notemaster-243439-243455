from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class Tag(BaseModel):
    id: UUID = Field(..., description="Tag UUID")
    name: str = Field(..., min_length=1, max_length=64, description="Unique tag name")


class NoteBase(BaseModel):
    title: str = Field("", max_length=500, description="Note title")
    content: str = Field("", description="Note content (markdown/plaintext)")
    content_format: Literal["markdown", "plaintext"] = Field(
        "markdown", description="Format of note content"
    )
    is_pinned: bool = Field(False, description="Pinned note appears at the top")
    is_favorite: bool = Field(False, description="Favorite note flag")
    tags: List[str] = Field(default_factory=list, description="List of tag names")


class NoteCreate(NoteBase):
    title: str = Field("Untitled", max_length=500, description="Note title")


class NoteUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500, description="Note title")
    content: Optional[str] = Field(None, description="Note content")
    content_format: Optional[Literal["markdown", "plaintext"]] = Field(
        None, description="Format of note content"
    )
    is_pinned: Optional[bool] = Field(None, description="Pinned flag")
    is_favorite: Optional[bool] = Field(None, description="Favorite flag")
    tags: Optional[List[str]] = Field(
        None, description="Replace tags with this list (names)"
    )


class NoteOut(BaseModel):
    id: UUID = Field(..., description="Note UUID")
    title: str = Field(..., description="Note title")
    content: str = Field(..., description="Note content")
    content_format: str = Field(..., description="Note content format")
    is_pinned: bool = Field(..., description="Pinned flag")
    is_favorite: bool = Field(..., description="Favorite flag")
    created_at: datetime = Field(..., description="Created timestamp")
    updated_at: datetime = Field(..., description="Updated timestamp")
    tags: List[Tag] = Field(default_factory=list, description="Expanded tags")


class NoteListItem(BaseModel):
    id: UUID = Field(..., description="Note UUID")
    title: str = Field(..., description="Note title")
    is_pinned: bool = Field(..., description="Pinned flag")
    is_favorite: bool = Field(..., description="Favorite flag")
    updated_at: datetime = Field(..., description="Updated timestamp")
    tags: List[str] = Field(default_factory=list, description="Tag names")


class NotesListResponse(BaseModel):
    items: List[NoteListItem] = Field(..., description="Notes list items")
    total: int = Field(..., description="Total notes matched")


class TagsListResponse(BaseModel):
    items: List[Tag] = Field(..., description="All tags")
    total: int = Field(..., description="Total tags")
