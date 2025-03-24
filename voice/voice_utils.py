import os
import logging
import re
import uuid
import subprocess
from pathlib import Path
import aiofiles
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any
from datetime import datetime

# Пытаемся импортировать pydub, но готовы использовать альтернативу
try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    logging.warning("pydub не удалось импортировать. Используем прямые вызовы ffmpeg.")


logger = logging.getLogger(__name__)

# Создаем пул потоков для CPU-интенсивных операций с аудио
# Используем разумное число потоков, зависящее от числа ядер процессора
_audio_thread_pool = ThreadPoolExecutor(
    max_workers=min(4, os.cpu_count() or 2),
    thread_name_prefix="audio_worker"
)


# Проверяем наличие ffmpeg в системе
def check_ffmpeg_installed() -> bool:
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


def normalize_filename(filename: str) -> str:
    """
    Normalize a filename by removing non-alphanumeric characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Normalized filename
    """
    # Remove non-alphanumeric characters except for extension
    base_name, ext = os.path.splitext(filename)
    base_name = re.sub(r'[^\w\-_]', '_', base_name)
    return f"{base_name}{ext}"


def generate_temp_filename(extension: str = ".mp3", prefix: str = "voice_") -> str:
    """
    Generate a unique temporary filename.
    
    Args:
        extension: File extension (default: .mp3)
        prefix: Filename prefix (default: voice_)
        
    Returns:
        Unique filename
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    random_id = str(uuid.uuid4())[:8]
    return f"{prefix}{timestamp}_{random_id}{extension}"


async def save_file_async(data: bytes, filepath: Path) -> Path:
    """
    Save binary data to a file asynchronously.
    
    Args:
        data: Binary data to save
        filepath: Path to save to
        
    Returns:
        Path to the saved file
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(filepath, 'wb') as file:
        await file.write(data)
    return filepath


async def remove_file_async(filepath: Path) -> bool:
    """
    Remove a file asynchronously.
    
    Args:
        filepath: Path to the file to remove
        
    Returns:
        True if file was removed successfully, False otherwise
    """
    try:
        if os.path.exists(filepath):
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, os.remove, filepath)
            logger.debug(f"Removed temporary file: {filepath}")
            return True
    except Exception as e:
        logger.error(f"Error removing file {filepath}: {e}")
    return False


async def direct_ffmpeg_convert(
    source_path: Path, 
    target_format: str = "mp3",
    target_path: Optional[Path] = None
) -> Path:
    """
    Convert audio file using direct ffmpeg command.
    Used when pydub is not available.
    
    Args:
        source_path: Path to the source audio file
        target_format: Target format (default: mp3)
        target_path: Optional custom target path
        
    Returns:
        Path to the converted file
    """
    if not FFMPEG_AVAILABLE:
        raise RuntimeError(
            "ffmpeg не установлен. Установите его командой: brew install ffmpeg"
        )
    
    if target_path is None:
        target_path = source_path.with_suffix(f".{target_format}")
    
    cmd = [
        "ffmpeg", "-i", str(source_path), 
        "-y",  # Перезаписать выходной файл, если существует
        "-acodec", "libmp3lame" if target_format == "mp3" else target_format,
        str(target_path)
    ]
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        logger.error(f"ffmpeg error: {stderr.decode()}")
        raise RuntimeError(
            f"Ошибка конвертации через ffmpeg: {stderr.decode()}"
        )
    
    return target_path


async def convert_audio_format(
    source_path: Path, 
    target_format: str = "mp3",
    target_path: Optional[Path] = None
) -> Path:
    """
    Convert audio file to a different format.
    Uses pydub if available, otherwise falls back to direct ffmpeg.
    
    Args:
        source_path: Path to the source audio file
        target_format: Target format (default: mp3)
        target_path: Optional custom target path
        
    Returns:
        Path to the converted file
    """
    if target_path is None:
        target_path = source_path.with_suffix(f".{target_format}")
    
    # Если pydub недоступен, используем прямой вызов ffmpeg
    if not PYDUB_AVAILABLE:
        return await direct_ffmpeg_convert(source_path, target_format, target_path)
    
    # Определяем функцию конвертации для выполнения в пуле потоков
    def _convert():
        try:
            audio = AudioSegment.from_file(str(source_path))
            audio.export(str(target_path), format=target_format)
            return target_path
        except Exception as e:
            logger.exception(f"Error converting audio: {e}")
            raise
    
    # Запускаем CPU-интенсивную операцию в пуле потоков
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(_audio_thread_pool, _convert)
        return result
    except Exception as e:
        logger.warning(f"pydub conversion failed: {e}, using direct ffmpeg")
        return await direct_ffmpeg_convert(source_path, target_format, target_path)


async def trim_audio(
    source_path: Path, 
    max_duration_ms: int = 60000,
    target_path: Optional[Path] = None
) -> Path:
    """
    Trim audio file to maximum duration.
    Uses pydub if available, otherwise falls back to direct ffmpeg.
    
    Args:
        source_path: Path to the source audio file
        max_duration_ms: Maximum duration in milliseconds
        target_path: Optional custom target path
        
    Returns:
        Path to the trimmed file (same as source if no trimming needed)
    """
    # Если pydub недоступен, используем прямой вызов ffmpeg
    if not PYDUB_AVAILABLE:
        if target_path is None:
            output_path = source_path.with_name(f"trimmed_{source_path.name}")
        else:
            output_path = target_path
            
        # Вырезаем нужную длительность через ffmpeg
        cmd = [
            "ffmpeg", "-i", str(source_path),
            "-y", "-t", str(max_duration_ms/1000),
            str(output_path)
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.error(f"ffmpeg error when trimming: {stderr.decode()}")
            return source_path
        
        return output_path
    
    # Определяем функцию для выполнения в пуле потоков
    def _trim():
        try:
            audio = AudioSegment.from_file(str(source_path))
            
            if len(audio) <= max_duration_ms:
                return source_path
            
            if target_path is None:
                output_path = source_path.with_name(f"trimmed_{source_path.name}")
            else:
                output_path = target_path
            
            trimmed_audio = audio[:max_duration_ms]
            trimmed_audio.export(
                str(output_path), 
                format=source_path.suffix[1:] if source_path.suffix else "mp3"
            )
            return output_path
        except Exception as e:
            logger.exception(f"Error trimming audio: {e}")
            raise
    
    # Запускаем CPU-интенсивную операцию в пуле потоков
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(_audio_thread_pool, _trim)
        return result
    except Exception as e:
        logger.warning(f"pydub trimming failed: {e}, using direct ffmpeg")
        if target_path is None:
            output_path = source_path.with_name(f"trimmed_{source_path.name}")
        else:
            output_path = target_path
            
        # Вырезаем нужную длительность через ffmpeg
        cmd = [
            "ffmpeg", "-i", str(source_path),
            "-y", "-t", str(max_duration_ms/1000),
            str(output_path)
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.error(f"ffmpeg error when trimming: {stderr.decode()}")
            return source_path
        
        return output_path


async def change_audio_speed(
    source_path: Path,
    speed_factor: float = 1.0,
    target_path: Optional[Path] = None
) -> Path:
    """
    Change audio playback speed.
    Uses pydub if available, otherwise falls back to direct ffmpeg.
    
    Args:
        source_path: Path to the source audio file
        speed_factor: Speed multiplier (1.0 = normal, >1.0 = faster, <1.0 = slower)
        target_path: Optional custom target path
        
    Returns:
        Path to the modified file
    """
    if speed_factor == 1.0:
        return source_path
    
    if target_path is None:
        speed_str = f"{int(speed_factor*100)}"
        target_path = source_path.with_name(f"speed{speed_str}_{source_path.name}")
    
    # Если pydub недоступен, используем прямой вызов ffmpeg
    if not PYDUB_AVAILABLE:
        # Изменяем скорость с помощью фильтра atempo в ffmpeg
        # atempo принимает значения между 0.5 и 2.0
        if speed_factor < 0.5:
            # Для очень медленной скорости нужно использовать несколько фильтров
            tempo_filter = f"atempo=0.5,atempo={speed_factor/0.5}"
        elif speed_factor > 2.0:
            # Для очень быстрой скорости нужно использовать несколько фильтров
            tempo_filter = f"atempo=2.0,atempo={speed_factor/2.0}"
        else:
            tempo_filter = f"atempo={speed_factor}"
        
        cmd = [
            "ffmpeg", "-i", str(source_path),
            "-y", "-filter:a", tempo_filter,
            str(target_path)
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.error(f"ffmpeg error when changing speed: {stderr.decode()}")
            return source_path
        
        return target_path
    
    # Определяем функцию для выполнения в пуле потоков
    def _change_speed():
        try:
            audio = AudioSegment.from_file(str(source_path))
            
            # Изменяем скорость воспроизведения через frame_rate
            # Это более эффективно, чем изменение через эффекты
            new_frame_rate = int(audio.frame_rate * speed_factor)
            audio = audio._spawn(audio.raw_data, overrides={
                "frame_rate": new_frame_rate
            })
            
            # Экспортируем с исходным frame_rate для изменения скорости
            audio.export(
                str(target_path),
                format=source_path.suffix[1:] if source_path.suffix else "mp3"
            )
            return target_path
        except Exception as e:
            logger.exception(f"Error changing audio speed: {e}")
            raise
    
    # Запускаем CPU-интенсивную операцию в пуле потоков
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(_audio_thread_pool, _change_speed)
        return result
    except Exception as e:
        logger.warning(f"pydub speed change failed: {e}, using direct ffmpeg")
        # Изменяем скорость с помощью фильтра atempo в ffmpeg
        # atempo принимает значения между 0.5 и 2.0
        if speed_factor < 0.5:
            # Для очень медленной скорости нужно использовать несколько фильтров
            tempo_filter = f"atempo=0.5,atempo={speed_factor/0.5}"
        elif speed_factor > 2.0:
            # Для очень быстрой скорости нужно использовать несколько фильтров
            tempo_filter = f"atempo=2.0,atempo={speed_factor/2.0}"
        else:
            tempo_filter = f"atempo={speed_factor}"
        
        cmd = [
            "ffmpeg", "-i", str(source_path),
            "-y", "-filter:a", tempo_filter,
            str(target_path)
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.error(f"ffmpeg error when changing speed: {stderr.decode()}")
            return source_path
        
        return target_path
