import os
from dataclasses import dataclass
from typing import Optional
from pathlib import Path


@dataclass
class Settings:
    """Configuration settings for the application."""
    # Bot settings
    BOT_TOKEN: str
    
    # API keys
    OPENAI_API_KEY: Optional[str] = None
    TAVILY_API_KEY: Optional[str] = None
    
    # File paths
    VOICE_TEMP_PATH: Path = Path("./voice/temp")
    
    # Other settings
    DEBUG: bool = False


def load_settings_from_env() -> Settings:
    """Load settings from environment variables."""
    # Ensure required environment variables are set
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        raise ValueError("BOT_TOKEN environment variable must be set")
    
    # Create voice temp directory if it doesn't exist
    voice_temp_path = Path(os.getenv("VOICE_TEMP_PATH", "./voice/temp"))
    voice_temp_path.mkdir(parents=True, exist_ok=True)
    
    return Settings(
        BOT_TOKEN=bot_token,
        OPENAI_API_KEY=os.getenv("OPENAI_API_KEY"),
        TAVILY_API_KEY=os.getenv("TAVILY_API_KEY"),
        VOICE_TEMP_PATH=voice_temp_path,
        DEBUG=os.getenv("DEBUG", "false").lower() == "true",
    )


# Create settings instance
settings = load_settings_from_env()
