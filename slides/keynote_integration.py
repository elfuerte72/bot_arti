import asyncio
import logging
from typing import Dict, Any, Tuple, Optional, List

logger = logging.getLogger(__name__)

async def get_presentation_structure() -> Dict[str, Any]:
    """
    Получает структуру презентации - разделы, названия слайдов и т.д.
    
    Returns:
        Структурированные данные о презентации
    """
    script = """
    tell application "Keynote"
        set presentationData to {}
        if exists document 1 then
            tell document 1
                set docName to name
                set slideCount to count of slides
                set sectionInfo to {}
                
                -- Собираем информацию о слайдах и разделах
                repeat with i from 1 to slideCount
                    tell slide i
                        set slideTitle to ""
                        set slideBody to ""
                        
                        -- Пытаемся получить заголовок
                        try
                            tell text item 1
                                set slideTitle to object text
                            end tell
                        end try
                        
                        -- Пытаемся получить остальной текст
                        try
                            if count of text items > 1 then
                                repeat with j from 2 to count of text items
                                    tell text item j
                                        set slideBody to slideBody & object text & "\\n"
                                    end tell
                                end repeat
                            end if
                        end try
                        
                        -- Определяем, является ли слайд разделом
                        set isSection to false
                        if slideTitle starts with "Раздел" or slideTitle contains "." then
                            set isSection to true
                        end if
                        
                        -- Добавляем информацию о слайде
                        set slideInfo to {slide_num:i, title:slideTitle, body:slideBody, is_section:isSection}
                        set end of sectionInfo to slideInfo
                    end tell
                end repeat
                
                -- Формируем итоговую структуру
                set presentationData to {name:docName, slide_count:slideCount, slides:sectionInfo}
            end tell
        end if
        
        return presentationData as JSON
    end tell
    """
    
    success, result = await run_enhanced_applescript(script)
    
    if success:
        try:
            import json
            return json.loads(result)
        except Exception as e:
            logger.exception(f"Ошибка при разборе JSON: {e}")
            return {}
    else:
        logger.error(f"Ошибка при получении структуры презентации: {result}")
        return {}

async def run_enhanced_applescript(script: str) -> Tuple[bool, Optional[str]]:
    """
    Улучшенная версия запуска AppleScript с обработкой ошибок и повторными попытками.
    
    Args:
        script: AppleScript для выполнения
        
    Returns:
        Кортеж (успех, результат/сообщение об ошибке)
    """
    # Максимальное количество попыток
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            # Запуск AppleScript
            proc = await asyncio.create_subprocess_exec(
                "osascript", "-e", script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Ожидание завершения с таймаутом
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            except asyncio.TimeoutError:
                if proc.returncode is None:
                    proc.kill()
                logger.warning(f"Таймаут выполнения AppleScript (попытка {attempt+1}/{max_retries})")
                continue
            
            if proc.returncode != 0:
                error = stderr.decode('utf-8').strip()
                
                # Особые случаи ошибок, которые можно обработать
                if "Документ уже воспроизводится" in error or "Document is already playing" in error:
                    return True, '{"status": "already_playing"}'
                
                logger.warning(f"Ошибка AppleScript: {error} (попытка {attempt+1}/{max_retries})")
                
                # Если последняя попытка, возвращаем ошибку
                if attempt == max_retries - 1:
                    return False, error
                
                # Иначе ждем перед следующей попыткой
                await asyncio.sleep(0.5)
                continue
            
            result = stdout.decode('utf-8').strip()
            return True, result
            
        except Exception as e:
            logger.exception(f"Исключение при выполнении AppleScript: {e} (попытка {attempt+1}/{max_retries})")
            
            # Если последняя попытка, возвращаем ошибку
            if attempt == max_retries - 1:
                return False, str(e)
            
            # Иначе ждем перед следующей попыткой
            await asyncio.sleep(0.5)
    
    # Если все попытки не удались
    return False, "Превышено максимальное количество попыток" 