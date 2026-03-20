"""
PythGuard backend configuration.

All settings are loaded from environment variables or a .env file.
Sensitive values (API keys, tokens) are never hardcoded.
"""
from pydantic_settings import BaseSettings
from pydantic import Field


class PythGuardSettings(BaseSettings):
    """
    Centralized settings for the PythGuard backend.
    All values can be overridden via environment variables.
    """

    # ── Pyth Pro ──────────────────────────────────────────────
    pyth_pro_access_token: str = Field(
        default="",
        description="Pyth Pro access token — get one from the Pyth forum (DM CHOPPAtheSHARK)"
    )
    pyth_mcp_server_url: str = Field(
        default="https://mcp.pyth.network/mcp",
        description="Pyth Pro MCP server endpoint"
    )
    pyth_hermes_api_url: str = Field(
        default="https://hermes.pyth.network",
        description="Pyth Hermes REST API (free, no auth required)"
    )

    # ── Rust Reader ────────────────────────────────────────────
    rust_reader_base_url: str = Field(
        default="http://localhost:8001",
        description="Internal Rust reader HTTP bridge URL"
    )
    rust_reader_timeout_seconds: int = Field(
        default=10,
        description="Timeout for requests to the Rust reader"
    )

    # ── Risk Engine ────────────────────────────────────────────
    risk_score_polling_interval_seconds: int = Field(
        default=15,
        description="How often to recompute risk scores for active wallets"
    )
    high_risk_score_threshold: float = Field(
        default=75.0,
        description="Score at or above this value triggers a HIGH risk alert"
    )
    medium_risk_score_threshold: float = Field(
        default=45.0,
        description="Score at or above this value triggers a MEDIUM risk alert"
    )

    # ── API ────────────────────────────────────────────────────
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    api_cors_allowed_origins: list[str] = Field(
        default=["http://localhost:3000"],
        description="Frontend origins allowed by CORS"
    )

    # ── Confidence Interval Thresholds ────────────────────────
    confidence_ratio_high_risk_threshold: float = Field(
        default=0.005,
        description="Confidence ratio above this = HIGH oracle uncertainty"
    )
    confidence_ratio_medium_risk_threshold: float = Field(
        default=0.001,
        description="Confidence ratio above this = MEDIUM oracle uncertainty"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Singleton instance — import this throughout the app
settings = PythGuardSettings()
