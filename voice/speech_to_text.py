import logging
import asyncio
import os
import subprocess
from pathlib import Path

import openai
from openai import AsyncOpenAI

from config.settings import settings
from voice.voice_utils import convert_audio_format, remove_file_async

logger = logging.getLogger(__name__)

# Проверяем наличие ffmpeg в системе
def check_ffmpeg_installed():
    """Проверяет наличие ffmpeg в системе."""
    try:
        subprocess.run(
            ["ffmpeg", "-version"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
        return True
    except (FileNotFoundError, subprocess.SubprocessError):
        logger.warning("ffmpeg не найден. Установите его для обработки аудио.")
        return False

# Инициализация - проверяем ffmpeg
FFMPEG_AVAILABLE = check_ffmpeg_installed()

# Кэш для клиента API
_openai_client = None


async def get_openai_client() -> AsyncOpenAI:
    """
    Получить клиент OpenAI API с повторным использованием.
    
    Returns:
        AsyncOpenAI: Асинхронный клиент OpenAI API
    """
    global _openai_client
    if _openai_client is None:
        if not settings.OPENAI_API_KEY:
            raise ValueError("OpenAI API key is not set")
        _openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


async def transcribe_audio(file_path: str, retries: int = 2) -> str:
    """
    Transcribe audio file to text using OpenAI Whisper API.
    
    Args:
        file_path: Path to the audio file (OGG, MP3, etc.)
        retries: Number of retries for API errors
        
    Returns:
        Transcribed text
    """
    file_path = Path(file_path)
    converted_file_path = None

    try:
        # Check if API key is available
        if not settings.OPENAI_API_KEY:
            logger.error("OpenAI API key is not available")
            return "Не удалось распознать голосовое сообщение (API ключ не найден)"

        # Convert to MP3 if needed
        if file_path.suffix.lower() != '.mp3':
            logger.info(f"Converting {file_path.suffix} to MP3")
            try:
                converted_file_path = await convert_audio_format(file_path, "mp3")
                audio_file_path = converted_file_path
            except Exception as conv_err:
                logger.error(f"Error converting audio format: {conv_err}")
                return f"Ошибка конвертации аудио: {str(conv_err)}"
        else:
            audio_file_path = file_path
        
        # Get OpenAI client and transcribe
        try:
            client = await get_openai_client()
            
            async def _try_transcribe():
                with open(audio_file_path, "rb") as audio_file:
                    try:
                        result = await client.audio.transcriptions.create(
                            model="whisper-1",
                            file=audio_file,
                            language="ru"  # Default to Russian, can be changed
                        )
                        return result.text
                    except openai.RateLimitError as rate_err:
                        logger.warning(f"Rate limit exceeded: {rate_err}")
                        await asyncio.sleep(2)  # Backoff before retry
                        raise
                    except openai.APIError as api_err:
                        logger.error(f"OpenAI API error: {api_err}")
                        raise
            
            # Retry logic for API errors
            for attempt in range(retries + 1):
                try:
                    text = await _try_transcribe()
                    logger.info(f"Transcribed audio: {text[:30]}...")
                    return text
                except (openai.RateLimitError, openai.APIError) as e:
                    if attempt < retries:
                        wait_time = (attempt + 1) * 2  # Exponential backoff
                        logger.warning(
                            f"Transcription attempt {attempt + 1} failed, "
                            f"retrying in {wait_time}s: {str(e)}"
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        raise  # Reraise on last attempt
        
        except Exception as e:
            logger.exception(f"Error during transcription: {e}")
            return f"Ошибка распознавания речи: {str(e)}"
        
    except Exception as e:
        logger.exception(f"Unexpected error in transcribe_audio: {e}")
        return f"Непредвиденная ошибка: {str(e)}"
        
    finally:
        # Clean up converted file if it exists
        if converted_file_path:
            await remove_file_async(converted_file_path)


async def process_voice_message(file_path: str) -> str:
    """
    Process voice message for the bot.
    This function can be extended to add pre/post-processing.
    
    Args:
        file_path: Path to the voice message file
        
    Returns:
        Transcribed text
    """
    try:
        # Basic implementation just calls transcribe_audio
        text = await transcribe_audio(file_path)
        
        # Простая постобработка
        text = text.strip()
        
        # Если текст пустой, возвращаем информативное сообщение
        if not text:
            return "Не удалось распознать текст в голосовом сообщении"
            
        return text
    
    except Exception as e:
        logger.exception(f"Error processing voice message: {e}")
        return f"Ошибка обработки голосового сообщения: {str(e)}"
