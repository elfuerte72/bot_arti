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
            
            # Карта известных ошибок и их пользовательские описания
            error_map = {
                "Документ уже воспроизводится": "Презентация уже запущена.",
                "Document is already playing": "Презентация уже запущена.",
                "No document is open": "Нет открытой презентации.",
                "No such slide": "Такого слайда не существует.",
                "execution error": "Ошибка выполнения команды в Keynote."
            }
            
            # Поиск известных ошибок в сообщении
            for error_text, user_message in error_map.items():
                if error_text in error:
                    return False, user_message
            
            # Если ошибка не найдена в карте, возвращаем общее сообщение
            return False, "Ошибка при работе с Keynote. Проверьте статус презентации."
        
        result = stdout.decode('utf-8').strip()
        return True, result
        
    except Exception as e:
        logger.exception(f"Failed to execute AppleScript: {e}")
        return False, "Ошибка взаимодействия с Keynote: " + str(e)


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

async def speak_next_block(rate: float = 1.0) -> Dict[str, Any]:
    """
    Озвучить название (заголовок) текущего слайда.
    
    Args:
        rate: Скорость речи (1.0 - нормальная, <1.0 - медленнее, >1.0 - быстрее)
    
    Returns:
        Dictionary с результатом операции
    """
    global _current_slide_text
    
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
    
    # Получаем только первую строку текста (заголовок)
    paragraphs = [p for p in slide_text.split("\n") if p.strip()]
    
    if not paragraphs:
        return {
            "success": False,
            "message": "На текущем слайде нет текста для озвучивания"
        }
    
    # Берём только первый абзац (заголовок)
    title_text = paragraphs[0]
    
    return {
        "success": True,
        "message": f"Озвучиваю заголовок: {title_text}",
        "text_to_speak": title_text,
        "rate": rate
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

async def search_web(query: str) -> Dict[str, Any]:
    """
    Выполняет поиск информации в Интернете.
    
    Args:
        query: Поисковый запрос
        
    Returns:
        Словарь с результатами поиска
    """
    try:
        # Импортируем модуль поиска здесь, чтобы избежать циклических импортов
        from core.tavily_search import TavilyAPI
        
        # Выполняем поиск
        search_results = await TavilyAPI.search(query)
        
        # Форматируем результаты
        formatted_results = await TavilyAPI.format_search_results(search_results)
        
        # Если поиск успешен, извлекаем текст для озвучивания
        if search_results.get("success", False):
            text_to_speak = search_results.get("content", "")
            if not text_to_speak:
                # Если нет основного контента, берём первый результат
                results = search_results.get("results", [])
                if results:
                    text_to_speak = results[0].get("content", "")
            
            return {
                "success": True,
                "message": formatted_results,
                "text_to_speak": text_to_speak
            }
        else:
            return {
                "success": False,
                "message": formatted_results
            }
    
    except Exception as e:
        logger.exception(f"Ошибка при поиске в Интернете: {e}")
        return {
            "success": False,
            "message": f"Не удалось выполнить поиск: {str(e)}"
        }


async def handle_question(question: str) -> Dict[str, Any]:
    """
    Обрабатывает вопрос от пользователя.
    
    Args:
        question: Текст вопроса
        
    Returns:
        Словарь с ответом на вопрос
    """
    try:
        # Импортируем модуль обработки вопросов здесь, чтобы избежать циклических импортов
        from core.question_handler import QuestionHandler
        
        # Обрабатываем вопрос
        answer_data = await QuestionHandler.search_and_process_question(question)
        
        # Форматируем ответ
        formatted_answer = await QuestionHandler.format_answer(answer_data)
        
        # Если обработка успешна
        if answer_data.get("success", False):
            answer = answer_data.get("answer", "")
            return {
                "success": True,
                "message": formatted_answer,
                "text_to_speak": answer
            }
        else:
            return {
                "success": False,
                "message": formatted_answer
            }
    
    except Exception as e:
        logger.exception(f"Ошибка при обработке вопроса: {e}")
        return {
            "success": False,
            "message": f"Не удалось обработать вопрос: {str(e)}"
        }


async def _get_current_presentation_info() -> Dict[str, Any]:
    """
    Получает информацию о текущей презентации (название, количество слайдов).
    
    Returns:
        Словарь с информацией о презентации
    """
    script = """
    tell application "Keynote"
        set presInfo to {}
        if exists document 1 then
            set docName to name of document 1
            set slideCount to count of slides of document 1
            set curSlide to slide number of current slide
            set presInfo to {docName:docName, slideCount:slideCount, currentSlide:curSlide}
        end if
        return presInfo as JSON
    end tell
    """
    
    success, result = await run_applescript(script)
    if success:
        try:
            import json
            return json.loads(result)
        except Exception as e:
            logger.error(f"Ошибка при разборе JSON: {e}")
            return {}
    else:
        return {}


async def generate_summary() -> Dict[str, Any]:
    """
    Генерирует резюме по текущей презентации.
    
    Returns:
        Словарь с результатами генерации резюме
    """
    try:
        # Проверяем, запущен ли Keynote
        if not await is_keynote_running():
            return {
                "success": False,
                "message": "Keynote не запущен"
            }
        
        # Проверяем, есть ли активная презентация
        if not await is_presentation_active():
            return {
                "success": False,
                "message": "Нет активной презентации"
            }
        
        # Получаем информацию о презентации
        pres_info = await _get_current_presentation_info()
        presentation_name = pres_info.get("docName", "Без названия")
        slide_count = pres_info.get("slideCount", 0)
        current_slide = pres_info.get("currentSlide", 0)
        
        # Получаем текст текущего слайда
        success, current_text = await get_current_slide_text()
        
        # Импортируем клиент OpenAI
        from core.question_handler import get_openai_client
        
        client = await get_openai_client()
        
        # Подготавливаем запрос к GPT-4
        system_prompt = """
        Ты - ассистент для подведения итогов презентации. 
        Твоя задача - сформировать краткое резюме по проведенной части презентации.
        Резюме должно быть структурированным, кратким и информативным.
        """
        
        user_prompt = f"""
        Подведи промежуточные итоги презентации со следующей информацией:
        - Название презентации: {presentation_name}
        - Всего слайдов: {slide_count}
        - Текущий слайд: {current_slide} из {slide_count}
        - Текст текущего слайда: {current_text if success else "Недоступен"}
        
        Сформируй резюме в формате:
        1. Какая часть презентации завершена (в процентах)
        2. Ключевые моменты, которые уже были рассмотрены
        3. Что еще предстоит рассмотреть
        
        Пиши кратко, четко, структурированно.
        """
        
        # Запрос к API
        response = await client.chat.completions.create(
            model="gpt-4-turbo", 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        summary = response.choices[0].message.content
        
        return {
            "success": True,
            "message": f"📊 Резюме презентации \"{presentation_name}\":\n\n{summary}",
            "text_to_speak": summary
        }
        
    except Exception as e:
        logger.exception(f"Ошибка при генерации резюме: {e}")
        return {
            "success": False,
            "message": f"Не удалось сгенерировать резюме: {str(e)}"
        }

async def goto_slide(slide_number: int = None, slide_title: str = None) -> Dict[str, Any]:
    """
    Переход к определенному слайду по номеру или названию.
    
    Args:
        slide_number: Номер слайда
        slide_title: Название или часть текста слайда
        
    Returns:
        Dictionary with status info
    """
    # Обеспечиваем наличие запущенного Keynote
    if not await ensure_keynote_running():
        return {
            "success": False,
            "message": "Keynote не запущен или не может быть запущен"
        }
    
    # Проверяем, есть ли презентация
    if not await is_presentation_active():
        return {
            "success": False,
            "message": "Нет активной презентации в Keynote"
        }
    
    # Проверяем, нужно ли сначала запустить презентацию
    is_playing = await is_presentation_playing()
    if not is_playing:
        # Запускаем презентацию если она не запущена
        start_result = await start_presentation()
        if not start_result["success"]:
            return start_result
    
    # Если указан номер слайда, переходим по номеру
    if slide_number is not None:
        return await goto_slide_by_number(slide_number)
    
    # Если указано название/текст, ищем подходящий слайд
    elif slide_title is not None:
        return await goto_slide_by_content(slide_title)
    
    # Если ни номер, ни название не указаны
    return {
        "success": False,
        "message": "Укажите номер слайда или текст для поиска"
    }

async def goto_slide_by_number(slide_number: int) -> Dict[str, Any]:
    """Переход к слайду по номеру."""
    # Получаем информацию о презентации
    info = await _get_current_presentation_info()
    
    # Проверяем, существует ли такой слайд
    if not info or "slideCount" not in info:
        return {
            "success": False,
            "message": "Не удалось получить информацию о презентации"
        }
    
    total_slides = info["slideCount"]
    
    if slide_number < 1 or slide_number > total_slides:
        return {
            "success": False,
            "message": f"Слайд {slide_number} не существует. Всего слайдов: {total_slides}"
        }
    
    # Переходим к слайду
    script = f'tell application "Keynote" to show slide {slide_number} of document 1'
    success, message = await run_applescript(script)
    
    if success:
        return {
            "success": True,
            "message": f"Переход к слайду {slide_number}"
        }
    else:
        return {
            "success": False,
            "message": f"Ошибка перехода к слайду {slide_number}: {message}"
        }

async def goto_slide_by_content(content_text: str) -> Dict[str, Any]:
    """Поиск и переход к слайду по содержимому."""
    # Получаем данные всех слайдов
    all_slides = await _get_all_slides_content()
    
    if not all_slides:
        return {
            "success": False,
            "message": "Не удалось получить содержимое слайдов"
        }
    
    # Ищем наиболее подходящий слайд
    best_match = None
    best_score = 0
    
    for slide_num, slide_text in all_slides.items():
        # Проверяем точное совпадение
        if content_text.lower() in slide_text.lower():
            score = len(content_text) / len(slide_text) * 100
            if score > best_score:
                best_score = score
                best_match = slide_num
    
    # Если есть совпадение, переходим к этому слайду
    if best_match:
        return await goto_slide_by_number(int(best_match))
    
    # Если слайд не найден
    return {
        "success": False,
        "message": f"Слайд с текстом '{content_text}' не найден"
    }

async def is_presentation_playing() -> bool:
    """
    Проверяет, воспроизводится ли презентация в данный момент.
    
    Returns:
        True если презентация воспроизводится, False иначе
    """
    if not await is_keynote_running():
        return False
    
    script = """
    tell application "Keynote"
        if playing then
            return "true"
        else
            return "false"
        end if
    end tell
    """
    success, result = await run_applescript(script)
    return success and result.lower() == "true"

async def _get_all_slides_content() -> Dict[str, str]:
    """
    Получает содержимое всех слайдов презентации.
    
    Returns:
        Словарь {номер_слайда: текст_слайда}
    """
    script = """
    tell application "Keynote"
        set slideContents to {}
        tell document 1
            set slideCount to count of slides
            repeat with i from 1 to slideCount
                tell slide i
                    set slideText to ""
                    repeat with t from 1 to count of text items
                        set slideText to slideText & (object text of text item t) & " "
                    end repeat
                end tell
                set end of slideContents to i & ":" & slideText
            end repeat
        end tell
        return slideContents as string
    end tell
    """
    
    success, result = await run_applescript(script)
    
    if not success or not result:
        return {}
    
    # Парсим результат
    slides = {}
    for line in result.split(", "):
        if ":" in line:
            num, text = line.split(":", 1)
            slides[num.strip()] = text.strip()
    
    return slides
