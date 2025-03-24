import asyncio
import logging
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)


async def run_applescript(script: str) -> Tuple[bool, Optional[str]]:
    """
    Run AppleScript command asynchronously.
    
    Args:
        script: AppleScript command to execute
        
    Returns:
        Tuple of (success, result/error message)
    """
    try:
        # Run process in separate thread to avoid blocking event loop
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Wait for command to complete and capture output
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            error = stderr.decode('utf-8').strip()
            logger.error(f"AppleScript error: {error}")
            return False, error
        
        result = stdout.decode('utf-8').strip()
        return True, result
        
    except Exception as e:
        logger.exception(f"Failed to execute AppleScript: {e}")
        return False, str(e)


async def is_keynote_running() -> bool:
    """
    Check if Keynote is currently running.
    
    Returns:
        True if Keynote is running, False otherwise
    """
    script = """
    tell application "System Events"
        return (exists process "Keynote")
    end tell
    """
    success, result = await run_applescript(script)
    return success and result.lower() == "true"


async def ensure_keynote_running() -> bool:
    """
    Ensure Keynote is running. Launch it if it's not running.
    
    Returns:
        True if Keynote is running or successfully launched, False otherwise
    """
    if await is_keynote_running():
        return True
    
    logger.info("Launching Keynote application...")
    script = 'tell application "Keynote" to activate'
    success, _ = await run_applescript(script)
    
    # Wait briefly for Keynote to start
    if success:
        await asyncio.sleep(2)
        return await is_keynote_running()
    
    return False


async def is_presentation_active() -> bool:
    """
    Check if a presentation is currently active in Keynote.
    
    Returns:
        True if a presentation is active, False otherwise
    """
    script = """
    tell application "Keynote"
        return (exists document 1)
    end tell
    """
    success, result = await run_applescript(script)
    return success and result.lower() == "true"


async def next_slide() -> Dict[str, Any]:
    """
    Advance to the next slide in Keynote.
    
    Returns:
        Dictionary with status info
    """
    if not await ensure_keynote_running():
        return {
            "success": False,
            "message": "Keynote не запущен или не может быть запущен"
        }
    
    if not await is_presentation_active():
        return {
            "success": False,
            "message": "Нет активной презентации в Keynote"
        }
    
    script = 'tell application "Keynote" to show next'
    success, message = await run_applescript(script)
    
    if success:
        return {
            "success": True,
            "message": "Переход к следующему слайду выполнен"
        }
    else:
        return {
            "success": False,
            "message": f"Ошибка перехода к следующему слайду: {message}"
        }


async def previous_slide() -> Dict[str, Any]:
    """
    Go back to the previous slide in Keynote.
    
    Returns:
        Dictionary with status info
    """
    if not await ensure_keynote_running():
        return {
            "success": False,
            "message": "Keynote не запущен или не может быть запущен"
        }
    
    if not await is_presentation_active():
        return {
            "success": False,
            "message": "Нет активной презентации в Keynote"
        }
    
    script = 'tell application "Keynote" to show previous'
    success, message = await run_applescript(script)
    
    if success:
        return {
            "success": True,
            "message": "Переход к предыдущему слайду выполнен"
        }
    else:
        return {
            "success": False,
            "message": f"Ошибка перехода к предыдущему слайду: {message}"
        }


async def start_presentation() -> Dict[str, Any]:
    """
    Start the presentation in Keynote.
    
    Returns:
        Dictionary with status info
    """
    if not await ensure_keynote_running():
        return {
            "success": False,
            "message": "Keynote не запущен или не может быть запущен"
        }
    
    script = 'tell application "Keynote" to start front document'
    success, message = await run_applescript(script)
    
    if success:
        return {
            "success": True,
            "message": "Презентация запущена"
        }
    else:
        return {
            "success": False,
            "message": f"Ошибка запуска презентации: {message}"
        }


async def end_presentation() -> Dict[str, Any]:
    """
    Stop the current Keynote presentation.
    
    Returns:
        Dictionary with status info
    """
    if not await is_keynote_running():
        return {
            "success": False,
            "message": "Keynote не запущен"
        }
    
    script = 'tell application "Keynote" to stop the slideshow'
    success, message = await run_applescript(script)
    
    if success:
        return {
            "success": True,
            "message": "Презентация остановлена"
        }
    else:
        return {
            "success": False,
            "message": f"Ошибка остановки презентации: {message}"
        }


async def pause_presentation() -> Dict[str, Any]:
    """
    Pause/Resume the current Keynote presentation.
    
    Returns:
        Dictionary with status info
    """
    if not await is_keynote_running():
        return {
            "success": False,
            "message": "Keynote не запущен"
        }
    
    # Check if presentation is playing
    playing_script = """
    tell application "Keynote"
        if playing then
            return "playing"
        else
            return "paused"
        end if
    end tell
    """
    success, status = await run_applescript(playing_script)
    
    if not success:
        return {
            "success": False,
            "message": "Не удалось определить статус презентации"
        }
    
    # Toggle pause/resume
    if status == "playing":
        script = 'tell application "Keynote" to pause slideshow'
        action = "остановлена"
    else:
        script = 'tell application "Keynote" to resume slideshow'
        action = "возобновлена"
    
    success, message = await run_applescript(script)
    
    if success:
        return {
            "success": True,
            "message": f"Презентация {action}"
        }
    else:
        return {
            "success": False,
            "message": f"Ошибка при изменении статуса презентации: {message}"
        }


async def get_presentation_status() -> Dict[str, Any]:
    """
    Get the current status of the Keynote presentation.
    
    Returns:
        Dictionary with status info
    """
    if not await is_keynote_running():
        return {
            "success": False,
            "message": "Keynote не запущен"
        }
    
    # Check if document exists
    doc_script = """
    tell application "Keynote"
        set doc_count to count of documents
        if doc_count > 0 then
            set doc_name to name of document 1
            set is_playing to playing
            set current_slide_num to 0
            set total_slides to 0
            if is_playing then
                tell document 1
                    set current_slide_num to slide number of current slide
                    set total_slides to count of slides
                end tell
            end if
            return doc_name & "|" & is_playing & "|" & current_slide_num & "|" & total_slides
        else
            return "no_document"
        end if
    end tell
    """
    success, result = await run_applescript(doc_script)
    
    if not success:
        return {
            "success": False,
            "message": f"Ошибка получения статуса: {result}"
        }
    
    if result == "no_document":
        return {
            "success": True,
            "message": "Нет открытых презентаций в Keynote"
        }
    
    # Parse results
    try:
        doc_name, is_playing, current_slide, total_slides = result.split("|")
        is_playing = is_playing.lower() == "true"
        current_slide = int(current_slide)
        total_slides = int(total_slides)
        
        status_text = f"Презентация: {doc_name}\n"
        status_text += f"Статус: {'Воспроизводится' if is_playing else 'Остановлена'}\n"
        if current_slide > 0:
            status_text += f"Слайд: {current_slide} из {total_slides}"
        
        return {
            "success": True,
            "message": status_text,
            "data": {
                "document_name": doc_name,
                "is_playing": is_playing,
                "current_slide": current_slide,
                "total_slides": total_slides
            }
        }
    except Exception as e:
        logger.exception(f"Error parsing presentation status: {e}")
        return {
            "success": False,
            "message": f"Ошибка обработки статуса презентации: {str(e)}"
        }

# Буфер для хранения текущего текста слайда
_current_slide_text = None
_last_spoken_text = None

async def get_current_slide_text() -> Tuple[bool, str]:
    """
    Получить текст с текущего слайда.
    
    Returns:
        Tuple[bool, str]: (успех, текст слайда/сообщение об ошибке)
    """
    global _current_slide_text
    
    if not await is_keynote_running():
        return False, "Keynote не запущен"
    
    if not await is_presentation_active():
        return False, "Нет активной презентации"
    
    # Получаем текст со слайда через AppleScript
    script = """
    tell application "Keynote"
        set slideText to ""
        tell document 1
            set currentSlideNumber to slide number of current slide
            tell slide currentSlideNumber
                repeat with i from 1 to count of text items
                    set slideText to slideText & (object text of text item i) & "\n"
                end repeat
            end tell
        end tell
        return slideText
    end tell
    """
    
    success, result = await run_applescript(script)
    
    if success:
        # Сохраняем текст в буфер
        _current_slide_text = result
        return True, result
    else:
        return False, f"Ошибка получения текста слайда: {result}"

async def speak_next_block() -> Dict[str, Any]:
    """
    Озвучить следующий блок текста со слайда.
    
    Returns:
        Dictionary с результатом операции
    """
    global _current_slide_text, _last_spoken_text
    
    # Получаем текст текущего слайда
    success, slide_text = await get_current_slide_text()
    
    if not success:
        return {
            "success": False,
            "message": slide_text  # slide_text содержит сообщение об ошибке
        }
    
    if not slide_text or slide_text.strip() == "":
        return {
            "success": False,
            "message": "На текущем слайде нет текста для озвучивания"
        }
    
    # Разбиваем текст на абзацы
    paragraphs = [p for p in slide_text.split("\n") if p.strip()]
    
    if not paragraphs:
        return {
            "success": False,
            "message": "На текущем слайде нет текста для озвучивания"
        }
    
    # Выбираем первый абзац, если ещё ничего не озвучено
    if _last_spoken_text is None:
        text_to_speak = paragraphs[0]
    else:
        # Находим индекс последнего озвученного блока
        try:
            last_index = -1
            for i, p in enumerate(paragraphs):
                if p == _last_spoken_text:
                    last_index = i
                    break
            
            # Если нашли и есть следующий блок
            if last_index >= 0 and last_index < len(paragraphs) - 1:
                text_to_speak = paragraphs[last_index + 1]
            else:
                # Если не нашли или это был последний блок, начинаем сначала
                text_to_speak = paragraphs[0]
        except Exception as e:
            logger.exception(f"Error selecting next block to speak: {e}")
            text_to_speak = paragraphs[0]
    
    # Сохраняем озвученный текст
    _last_spoken_text = text_to_speak
    
    return {
        "success": True,
        "message": f"Озвучиваю: {text_to_speak}",
        "text_to_speak": text_to_speak
    }

async def repeat_last_block() -> Dict[str, Any]:
    """
    Повторить последний озвученный блок текста.
    
    Returns:
        Dictionary с результатом операции
    """
    global _last_spoken_text
    
    if _last_spoken_text is None:
        # Если еще ничего не озвучивалось, озвучиваем первый блок
        return await speak_next_block()
    
    return {
        "success": True,
        "message": f"Повторяю: {_last_spoken_text}",
        "text_to_speak": _last_spoken_text
    }

async def handle_question(question_text: str) -> Dict[str, Any]:
    """
    Обработать вопрос из аудитории, связанный с текущим слайдом.
    
    Args:
        question_text: Текст вопроса
        
    Returns:
        Dictionary с результатом операции
    """
    # Получаем текст текущего слайда для контекста
    success, slide_text = await get_current_slide_text()
    
    if not success:
        return {
            "success": False,
            "message": f"Не удалось получить контекст слайда: {slide_text}"
        }
    
    # Формируем информацию для ответа на вопрос
    context = {
        "success": True,
        "message": "Вопрос обработан",
        "question": question_text,
        "slide_context": slide_text or "Текст слайда недоступен",
        "needs_ai_processing": True  # Флаг для внешней обработки вопроса через AI
    }
    
    return context
