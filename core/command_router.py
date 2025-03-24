from typing import Dict, Any, List, Tuple
import re
import logging
import os
from dotenv import load_dotenv
import openai
import asyncio

from slides import keynote_controller

# Загрузка переменных окружения
load_dotenv()

# Инициализация API ключа OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

logger = logging.getLogger(__name__)

# Маппинг команд с ключевыми словами и синонимами
COMMAND_PATTERNS: Dict[str, List[Tuple[str, float]]] = {
    "next_slide": [
        (r"\b(next|forward|следующий|вперед|далее)\s+(slide|слайд)\b", 0.95),
        (r"\b(next|forward|следующий|вперед|далее)\b", 0.85),
        (r"\bслед(ующий)?\s+слайд\b", 0.95),
    ],
    "previous_slide": [
        (r"\b(previous|back|назад|предыдущий)\s+(slide|слайд)\b", 0.95),
        (r"\b(previous|back|назад|предыдущий)\b", 0.85),
        (r"\bпред(ыдущий)?\s+слайд\b", 0.95),
    ],
    "pause": [
        (r"\b(pause|stop|пауза|стоп|остановить)\b", 0.9),
    ],
    "resume": [
        (r"\b(continue|resume|продолжить|продолжай|возобновить)\b", 0.9),
    ],
    "start": [
        (r"\b(start|begin|начать|запустить|начни)\s+"
         r"(presentation|презентацию|показ|семинар)\b", 0.95),
        (r"\b(begin|start|начни семинар)\b", 0.8),
    ],
    "end_presentation": [
        (r"\b(end|finish|закончить|завершить)\s+"
         r"(presentation|презентацию|показ)\b", 0.95),
        (r"\b(end|finish|exit|quit|выход|выйти)\b", 0.8),
    ],
    "speak_next_block": [
        (r"\b(говори|читай|озвучь|скажи)\b", 0.9),
    ],
    "repeat_last_block": [
        (r"\b(повтори|повтор|еще раз)\b", 0.9),
    ],
    "handle_question": [
        (r"\b(ответь|ответить)\s+(на)?\s*(вопрос|запрос)\b", 0.95),
    ],
}

# Маппинг названий команд на функции контроллера
COMMAND_FUNCTIONS = {
    "next_slide": keynote_controller.next_slide,
    "previous_slide": keynote_controller.previous_slide,
    "pause": keynote_controller.pause_presentation,
    "resume": keynote_controller.pause_presentation,
    "start": keynote_controller.start_presentation,
    "end_presentation": keynote_controller.end_presentation,
    "status": keynote_controller.get_presentation_status,
    # Добавляем реализованные функции
    "speak_next_block": keynote_controller.speak_next_block,
    "repeat_last_block": keynote_controller.repeat_last_block,
    "handle_question": None,  # Эта функция вызывается особым образом
}

async def use_openai_for_intent(text: str) -> Dict[str, Any]:
    """
    Использовать OpenAI для определения намерения, когда стандартные паттерны не сработали.
    
    Args:
        text: Текст для анализа
        
    Returns:
        Словарь с действием и уровнем уверенности
    """
    try:
        actions = list(COMMAND_PATTERNS.keys())
        
        system_prompt = """
        Ты - система распознавания команд для ассистента семинара. 
        Твоя задача - определить намерение пользователя из текста на русском языке.
        """
        
        user_prompt = f"""
        Пожалуйста, определи, какое намерение соответствует следующему тексту: 
        "{text}"
        
        Выбери одно из следующих намерений:
        {', '.join(actions)}
        
        Если текст не соответствует ни одному из намерений, верни "unknown".
        Ответь только название намерения, без дополнительного текста.
        """
        
        try:
            response = openai.chat.completions.create(
                model="gpt-4-1106-preview",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                top_p=0.9,
                max_tokens=50,
                frequency_penalty=0.0,
                presence_penalty=0.0
            )
            
            intent = response.choices[0].message.content.strip().lower()
            
            # Проверяем, есть ли распознанное намерение в списке доступных
            if intent in actions:
                return {"action": intent, "confidence": 0.7}
            
            return {"action": "unknown", "confidence": 0.0}
            
        except openai.RateLimitError:
            logger.warning("OpenAI API rate limit exceeded. Waiting and retrying...")
            await asyncio.sleep(2)  # Пауза перед повторной попыткой
            # Используем fall-back модель при повторной попытке
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",  # Fall-back на менее мощную модель
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=50
            )
            
            intent = response.choices[0].message.content.strip().lower()
            
            if intent in actions:
                return {"action": intent, "confidence": 0.6}  # Меньше уверенности для fall-back модели
            
            return {"action": "unknown", "confidence": 0.0}
            
        except (openai.APIError, openai.APIConnectionError) as api_err:
            logger.error(f"OpenAI API ошибка: {api_err}")
            return {"action": "unknown", "confidence": 0.0, "error": str(api_err)}
            
    except Exception as e:
        logger.exception(f"Ошибка при обращении к OpenAI API: {e}")
        return {"action": "unknown", "confidence": 0.0, "error": str(e)}

async def extract_question(text: str) -> str:
    """
    Извлекает вопрос из текста пользователя.
    
    Args:
        text: Текст сообщения пользователя
        
    Returns:
        Извлеченный вопрос или исходный текст
    """
    # Паттерны для извлечения вопроса после ключевых слов
    patterns = [
        r"(?:ответь на|ответить на|ответь|обработай|вопрос:?)\s*(.+)$",
        r"(?:вопрос из аудитории:?)\s*(.+)$",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    # Если не нашли специфический паттерн, возвращаем весь текст
    return text

async def handle_command(text: str) -> Dict[str, Any]:
    """
    Распознать и обработать команду пользователя.
    
    Args:
        text: Текст для анализа
        
    Returns:
        Словарь с действием и уровнем уверенности
    """
    # Нормализация текста - приведение к нижнему регистру и удаление лишних пробелов
    normalized_text = text.lower().strip()
    
    highest_confidence = 0.0
    best_action = "unknown"
    
    # Проверка каждого шаблона команды
    for action, patterns in COMMAND_PATTERNS.items():
        for pattern, confidence in patterns:
            if re.search(pattern, normalized_text):
                if confidence > highest_confidence:
                    highest_confidence = confidence
                    best_action = action
    
    # Если не удалось найти совпадений с высокой уверенностью, используем OpenAI
    if highest_confidence < 0.7:
        openai_result = await use_openai_for_intent(normalized_text)
        if openai_result["confidence"] > highest_confidence:
            best_action = openai_result["action"]
            highest_confidence = openai_result["confidence"]
    
    result = {
        "action": best_action,
        "confidence": highest_confidence
    }
    
    # Если уверенность достаточно высока и есть функция для выполнения команды
    if highest_confidence >= 0.7 and best_action != "unknown":
        try:
            # Специальная обработка для команды вопроса
            if best_action == "handle_question":
                question = await extract_question(text)
                command_func = keynote_controller.handle_question
                execution_result = await command_func(question)
            else:
                command_func = COMMAND_FUNCTIONS.get(best_action)
                if command_func and callable(command_func):
                    execution_result = await command_func()
                else:
                    execution_result = {
                        "success": False,
                        "message": f"Функция для команды '{best_action}' не реализована"
                    }
            
            result["execution_result"] = execution_result
        except Exception as e:
            logger.exception(f"Ошибка при выполнении команды '{best_action}': {e}")
            result["execution_result"] = {
                "success": False,
                "message": f"Ошибка при выполнении: {str(e)}"
            }
    
    return result
