import logging
from pathlib import Path
from typing import Optional, Dict, List

import edge_tts

from config.settings import settings
from voice.voice_utils import generate_temp_filename

logger = logging.getLogger(__name__)

# Available voices cache
_AVAILABLE_VOICES: Optional[List[Dict[str, str]]] = None


async def get_available_voices() -> List[Dict[str, str]]:
    """
    Get list of available voices from Edge TTS.
    
    Returns:
        List of voice dictionaries
    """
    global _AVAILABLE_VOICES
    
    if _AVAILABLE_VOICES is None:
        _AVAILABLE_VOICES = await edge_tts.list_voices()
        logger.info(f"Loaded {len(_AVAILABLE_VOICES)} voices from Edge TTS")
    
    return _AVAILABLE_VOICES


async def get_voice_by_locale(locale: str = "ru-RU") -> str:
    """
    Get the first voice for a given locale.
    
    Args:
        locale: Locale code (e.g., "ru-RU", "en-US")
        
    Returns:
        Voice name or default voice if not found
    """
    voices = await get_available_voices()
    
    # Find matching voice
    for voice in voices:
        if voice.get("Locale", "").lower() == locale.lower():
            return voice.get("ShortName")
    
    # Default to first Russian voice or English if not found
    default_voices = {
        "ru-RU": "ru-RU-SvetlanaNeural",
        "en-US": "en-US-AriaNeural"
    }
    
    return default_voices.get(locale, "en-US-AriaNeural")


async def synthesize_speech(
    text: str,
    voice: str = "ru-RU-SvetlanaNeural",
    rate: float = 1.0,
    output_dir: Optional[Path] = None
) -> str:
    """
    Synthesize speech from text using Edge TTS.
    
    Args:
        text: Text to synthesize
        voice: Voice identifier (default: ru-RU-SvetlanaNeural)
        rate: Speech rate (default: 1.0)
        output_dir: Directory to save file (default: settings.VOICE_TEMP_PATH)
        
    Returns:
        Path to generated audio file
    """
    if not output_dir:
        output_dir = settings.VOICE_TEMP_PATH
        output_dir.mkdir(exist_ok=True, parents=True)
    
    # Generate output file path
    output_file = output_dir / generate_temp_filename()
    
    try:
        # Configure communication
        if abs(rate - 1.0) < 0.01:  # Если rate близок к 1.0
            rate_option = "+0%"
        else:
            rate_option = f"+{int((rate-1)*100)}%" if rate > 1.0 else f"{int((rate-1)*100)}%"
        
        logger.debug(f"Using rate option: {rate_option} for rate value: {rate}")
        
        tts = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=rate_option
        )
        
        # Generate speech
        await tts.save(str(output_file))
        logger.info(f"Generated speech file: {output_file}")
        
        # Return file path as string
        return str(output_file)
        
    except Exception as e:
        logger.exception(f"Error generating speech: {e}")
        raise


async def synthesize_response(
    text: str,
    voice: Optional[str] = None,
    rate: float = 1.0
) -> str:
    """
    Helper function to synthesize bot responses.
    Auto-selects appropriate voice based on text language.
    
    Args:
        text: Text to synthesize
        voice: Voice identifier (if None, auto-selected based on text)
        rate: Speech rate (default: 1.0)
        
    Returns:
        Path to generated audio file
    """
    # If voice not specified, auto-detect language and select voice
    if voice is None:
        # Simple language detection - can be replaced with more sophisticated approach
        has_cyrillic = any(
            ord('а') <= ord(c) <= ord('я') for c in text.lower()
        )
        locale = "ru-RU" if has_cyrillic else "en-US"
        voice = await get_voice_by_locale(locale)
    
    # Synthesize speech
    return await synthesize_speech(text, voice, rate)
