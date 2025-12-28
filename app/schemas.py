from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal

class Decision(BaseModel):
    text: str
    who: str | None = None
    when: str | None = None
    message_refs: list[int] = Field(default_factory=list)
    snippets: list[str] = Field(default_factory=list)

class Risk(BaseModel):
    text: str
    severity: Literal["low", "medium", "high"]
    status: Literal["open", "mitigating", "closed", "unknown"]
    message_refs: list[int] = Field(default_factory=list)
    snippets: list[str] = Field(default_factory=list)

class OpenQuestion(BaseModel):
    text: str
    message_refs: list[int] = Field(default_factory=list)
    snippets: list[str] = Field(default_factory=list)

class ActionItem(BaseModel):
    task: str
    owner: str | None = None
    deadline: str | None = None
    status: Literal["todo", "doing", "done", "unknown"]
    message_refs: list[int] = Field(default_factory=list)
    snippets: list[str] = Field(default_factory=list)

class NotableFact(BaseModel):
    text: str
    message_refs: list[int] = Field(default_factory=list)
    snippets: list[str] = Field(default_factory=list)

class Topic(BaseModel):
    topic: str
    summary: str
    message_refs: list[int] = Field(default_factory=list)

class SummaryJSON(BaseModel):
    decisions: list[Decision] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    open_questions: list[OpenQuestion] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    notable_facts: list[NotableFact] = Field(default_factory=list)
    topics: list[Topic] = Field(default_factory=list)
