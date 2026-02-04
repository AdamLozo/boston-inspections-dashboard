"""
Boston Food Inspections Dashboard - Configuration
Environment variable management for database and sync settings
"""

import os
from pathlib import Path

# Load .env file if it exists (for local development)
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    # python-dotenv not installed, skip loading .env
    pass


class Settings:
    """Application settings from environment variables"""

    # Database connection
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://localhost/boston_inspections"
    )

    # Sync job configuration
    SYNC_DAYS_BACK: int = int(os.getenv("SYNC_DAYS_BACK", "90"))

    # CKAN API configuration for Food Establishment Inspections
    CKAN_RESOURCE_ID: str = "4582bec6-2b4f-4f9e-bc55-cbaa73117f4c"
    CKAN_SQL_API_URL: str = "https://data.boston.gov/api/3/action/datastore_search_sql"

    # Server configuration
    PORT: int = int(os.getenv("PORT", "8000"))

    @property
    def is_production(self) -> bool:
        """Check if running in production (Render)"""
        return "render.com" in self.DATABASE_URL.lower()


settings = Settings()
