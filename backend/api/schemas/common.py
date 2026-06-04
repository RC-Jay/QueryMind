from pydantic import BaseModel


class DetailResponse(BaseModel):
    """Generic message response for actions that return a status string."""
    detail: str
