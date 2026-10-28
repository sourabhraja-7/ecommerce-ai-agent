"""
Pydantic schemas for the FastAPI gateway.
"""
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., description="The customer's message", min_length=1, max_length=2000)
    session_id: str = Field(default="default", description="Conversation ID (keeps multi-turn context)")


class ChatResponse(BaseModel):
    response: str = Field(..., description="The assistant's reply")
    intent: str = Field(default="general", description="Detected intent")
    order_id: str = Field(default="", description="Extracted order ID")
    tracking_number: str = Field(default="", description="Extracted tracking number")
    customer_email: str = Field(default="", description="Extracted email")
    tool_results: dict = Field(default_factory=dict, description="Raw tool call results")


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
