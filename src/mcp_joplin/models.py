"""Structured models returned by MCP tools."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PagedResult(BaseModel):
    items: list[dict[str, Any]]
    page: int = Field(ge=1)
    limit: int = Field(ge=1, le=100)
    has_more: bool
    next_page: int | None


class Note(BaseModel):
    id: str
    title: str | None = None
    body: str | None = None
    parent_id: str | None = None
    created_time: int | None = None
    updated_time: int | None = None


class NoteDetachResult(Note):
    """The note after detaching, plus how many references were removed (0 = untouched)."""

    links_removed: int = 0


class NoteEditResult(Note):
    """The note after a text replacement, plus how many occurrences were replaced."""

    replacements: int


class Folder(BaseModel):
    id: str
    title: str | None = None
    parent_id: str | None = None
    created_time: int | None = None
    updated_time: int | None = None


class Tag(BaseModel):
    id: str
    title: str | None = None


class Resource(BaseModel):
    id: str
    title: str | None = None
    mime: str | None = None
    filename: str | None = None
    file_extension: str | None = None
    size: int | None = None
    created_time: int | None = None
    updated_time: int | None = None


class ResourceBlob(BaseModel):
    id: str
    mime: str | None = None
    filename: str | None = None
    size: int
    data_base64: str


class FolderNode(BaseModel):
    id: str
    title: str | None = None
    children: list[FolderNode] = Field(default_factory=list)
