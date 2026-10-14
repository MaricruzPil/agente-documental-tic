from pydantic import BaseModel, Field

class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=3000)
    use_search: bool = True

class Source(BaseModel):
    name: str
    url: str | None = None

class AskResponse(BaseModel):
    success: bool
    answer: str
    sources: list[Source]
