from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        description="Texto que se desea analizar."
    )

    domain: str = Field(
        default="general",
        description="Dominio semántico del texto."
    )