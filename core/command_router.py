from typing import Dict, Any, List, Tuple
import re
import logging
import os
import time
from dotenv import load_dotenv
import openai
import asyncio

from slides import keynote_controller
from core.question_handler import QuestionHandler
from core.presentation_state import PresentationContext, PresentationState

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
        (r"\b(поищи|найди|загугли|поиск)\b", 0.9),
        (r"\b(что такое|кто такой|как|почему|зачем|когда)\b", 0.85),
    ],
    "search_web": [
        (r"\b(поиск|найди|загугли|найти)\s+(в)?\s*(интернете|сети|онлайн)\b", 0.95),
        (r"\b(посмотри|проверь)\s+(информацию|данные)\b", 0.9),
    ],
    "generate_summary": [
        (r"\b(резюме|резюмируй|подведи итоги|итоги)\b", 0.9),
        (r"\b(сделай|создай)\s+(резюме|отчет|выводы)\b", 0.95),
        (r"\b(о чем|информация|содержание|расскажи)\s+(презентация|презентации|доклад)\b", 0.9),
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
    "handle_question": keynote_controller.handle_question,
    "search_web": keynote_controller.search_web,
    "generate_summary": keynote_controller.generate_summary,
}

async def use_openai_for_intent(text: str) -> Dict[str, Any]:
    """
    Использовать OpenAI для определения намерения из текста команды.
    
    Args:
        text: Текст для анализа
        
    Returns:
        Словарь с действием и уровнем уверенности, или список таких словарей,
        если обнаружено несколько команд
    """
    try:
        actions = list(COMMAND_PATTERNS.keys()) + ["need_clarification"]
        
        system_prompt = """
        Ты - интеллектуальный ассистент для управления презентациями. 
        Твоя задача - понять намерение пользователя из его сообщения, 
        даже если оно выражено косвенно или в свободной форме.
        
        Пользователь может запрашивать несколько действий в одном сообщении.
        В этом случае тебе нужно определить все запрошенные действия и вернуть их
        в порядке упоминания в сообщении.
        
        Основные действия, которые ты можешь выполнять:
        - next_slide: переключение на следующий слайд
        - previous_slide: возврат к предыдущему слайду
        - pause: приостановка презентации
        - resume: продолжение презентации
        - start: начало презентации
        - end_presentation: завершение презентации
        - speak_next_block: чтение текста со слайда
        - repeat_last_block: повторение последнего прочитанного текста
        - handle_question: ответ на вопрос
        - search_web: поиск информации в интернете
        - generate_summary: создание резюме/сводки о презентации
        - status: получение текущего статуса презентации
        
        Используй "generate_summary" для запросов о содержании презентации, её теме, 
        информации о презентации, и т.п.
        
        Используй "handle_question" только для явных вопросов по теме, не связанных
        напрямую с управлением презентацией.
        
        Не выбирай "need_clarification", если можешь сопоставить запрос с одним
        из доступных действий. Выбирай наиболее подходящее действие из списка.
        """
        
        user_prompt = f"""
        Прошу определить намерение пользователя из следующего сообщения: 
        "{text}"
        
        Выбери одно или несколько намерений из следующих:
        {', '.join(actions)}
        
        Если в сообщении содержится несколько намерений, вернуть их в формате:
        намерение1, намерение2, намерение3
        
        Если сообщение не соответствует ни одному из намерений, верни "unknown".
        Учитывай контекст презентации и возможные косвенные указания 
        в речи пользователя.
        
        Ответь только названием намерения или списком намерений через запятую,
        без дополнительного текста.
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
                max_tokens=100,
                frequency_penalty=0.0,
                presence_penalty=0.0
            )
            
            intent_text = response.choices[0].message.content.strip().lower()
            
            # Проверяем, есть ли несколько намерений (разделенных запятыми)
            if ',' in intent_text:
                intents = [intent.strip() for intent in intent_text.split(',')]
                result = []
                
                for intent in intents:
                    if intent in actions:
                        result.append({"action": intent, "confidence": 0.85})
                    else:
                        result.append({"action": "unknown", "confidence": 0.0})
                
                return {"multiple_actions": True, "actions": result}
            
            # Обработка одиночного намерения
            intent = intent_text
            
            # Проверяем, есть ли распознанное намерение в списке доступных
            if intent in actions:
                # Распознанное ИИ намерение - возвращаем с высокой уверенностью
                return {"action": intent, "confidence": 0.85}
            
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
                max_tokens=100
            )
            
            intent_text = response.choices[0].message.content.strip().lower()
            
            # Проверяем, есть ли несколько намерений
            if ',' in intent_text:
                intents = [intent.strip() for intent in intent_text.split(',')]
                result = []
                
                for intent in intents:
                    if intent in actions:
                        result.append({"action": intent, "confidence": 0.75})
                    else:
                        result.append({"action": "unknown", "confidence": 0.0})
                
                return {"multiple_actions": True, "actions": result}
            
            # Обработка одиночного намерения
            intent = intent_text
            
            if intent in actions:
                # Меньше уверенности для fall-back модели
                return {"action": intent, "confidence": 0.75}
            
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

async def extract_parameters(text: str, action: str) -> Dict[str, Any]:
    """
    Извлекает параметры из текста сообщения на основе определенного действия.
    
    Args:
        text: Текст сообщения пользователя
        action: Определенное действие
        
    Returns:
        Словарь с параметрами для выполнения действия
    """
    params = {}
    
    # Для вопросов извлекаем текст вопроса
    if action == "handle_question":
        params["question"] = await extract_question(text)
    
    # Для поиска в Интернете извлекаем поисковой запрос
    elif action == "search_web":
        patterns = [
            r"(?:поиск|найди|загугли|найти|посмотри|проверь)(?:[^:]*):?\s*(.+)$",
            r"(?:в интернете|в сети|онлайн)\s*[о\s]*(.+)$",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                params["query"] = match.group(1).strip()
                break
        
        # Если не нашли по шаблону, используем весь текст
        if "query" not in params:
            params["query"] = text
    
    # Для переключения слайдов можно извлечь количество слайдов
    elif action in ["next_slide", "previous_slide"]:
        # Поиск числа слайдов для пропуска
        number_match = re.search(r'(\d+)\s+(слайд|slide)', text.lower())
        if number_match:
            try:
                params["slide_count"] = int(number_match.group(1))
            except ValueError:
                params["slide_count"] = 1
    
    # Для синтеза речи можно добавить скорость
    elif action in ["speak_next_block", "repeat_last_block"]:
        # Поиск модификаторов скорости
        if re.search(r'\b(медленн|slower|помедленнее)\b', text.lower()):
            params["rate"] = 0.8
        elif re.search(r'\b(быстр|faster|побыстрее)\b', text.lower()):
            params["rate"] = 1.2
    
    return params

async def identify_action(text: str, current_state: PresentationState = None) -> Dict[str, Any]:
    """
    Определяет намерение пользователя на основе текста и текущего состояния.
    
    Args:
        text: Текст для анализа
        current_state: Текущее состояние презентации
        
    Returns:
        Словарь с действием и уверенностью
    """
    # Используем GPT для понимания намерения пользователя
    try:
        # Формируем промпт с учетом контекста
        context_prompt = ""
        if current_state:
            context_prompt = f"\nТекущее состояние презентации: {current_state.value}."
            
            # Добавляем подсказки в зависимости от состояния
            if current_state == PresentationState.NO_KEYNOTE:
                context_prompt += "\nПользователю следует сначала запустить Keynote."
            elif current_state == PresentationState.NO_PRESENTATION:
                context_prompt += "\nПользователю нужно открыть презентацию в Keynote."
            elif current_state == PresentationState.READY:
                context_prompt += "\nПрезентация готова, но не запущена. Пользователь может захотеть начать презентацию."
            elif current_state == PresentationState.PLAYING:
                context_prompt += "\nПрезентация воспроизводится. Пользователь может хотеть перейти между слайдами или поставить на паузу."
            elif current_state == PresentationState.PAUSED:
                context_prompt += "\nПрезентация на паузе. Пользователь может хотеть возобновить воспроизведение."
        
        system_prompt = f"""
        Ты - интеллектуальный ассистент для управления презентациями. 
        Твоя задача - понять намерение пользователя из его сообщения, 
        даже если оно выражено косвенно или в свободной форме.
        {context_prompt}
        
        Пользователь может запрашивать несколько действий в одном сообщении.
        В этом случае тебе нужно определить все запрошенные действия и вернуть их
        в порядке упоминания в сообщении.
        
        Основные действия, которые ты можешь выполнять:
        - next_slide: переключение на следующий слайд
        - previous_slide: возврат к предыдущему слайду
        - pause: приостановка презентации
        - resume: продолжение презентации
        - start: начало презентации
        - end_presentation: завершение презентации
        - speak_next_block: чтение текста со слайда
        - repeat_last_block: повторение последнего прочитанного текста
        - handle_question: ответ на вопрос
        - search_web: поиск информации в интернете
        - generate_summary: создание резюме/сводки о презентации
        - status: получение текущего статуса презентации
        - goto_slide: переход к определенному слайду по номеру или содержанию
        
        Распознай слайды с номерами, например "покажи слайд 4" или упоминания разделов вроде "4. Здоровье" 
        как команду goto_slide.
        
        Не выбирай "need_clarification", если можешь сопоставить запрос с одним
        из доступных действий. Выбирай наиболее подходящее действие из списка.
        """
        
        # Остальной код для использования OpenAI API...
        # ...
        
    except Exception as e:
        logger.exception(f"Error using OpenAI for intent: {e}")
        # Используем запасной вариант с регулярными выражениями
        return await identify_action_with_regex(text, current_state)

async def handle_multiple_commands(text: str, actions_data: Dict[str, Any], context: PresentationContext) -> Dict[str, Any]:
    """
    Обработать несколько команд из одного сообщения пользователя с учетом контекста презентации.
    
    Args:
        text: Текст с командами
        actions_data: Данные о распознанных действиях
        context: Контекст презентации
        
    Returns:
        Словарь с результатами выполнения всех команд
    """
    actions = actions_data.get("actions", [])
    results = []
    
    # Обрабатываем каждое действие по отдельности
    for action_data in actions:
        action = action_data["action"]
        confidence = action_data["confidence"]
        
        # Пропускаем действия с низкой уверенностью
        if confidence < 0.5 or action == "unknown" or action == "need_clarification":
            continue
        
        # Проверяем, возможно ли выполнить действие в текущем состоянии
        validation = await context.validate_action(action)
        if not validation["valid"]:
            continue
        
        # Извлекаем параметры из текста для действия
        params = await extract_parameters(text, action)
        action_data["params"] = params
        
        # Если функция существует, вызываем её
        if action in COMMAND_FUNCTIONS:
            try:
                # Передаем параметры и контекст в функцию
                fn = COMMAND_FUNCTIONS[action]
                
                # Проверяем подпись функции
                import inspect
                sig = inspect.signature(fn)
                
                # Фильтруем параметры, оставляя только те, которые есть в сигнатуре функции
                supported_params = {}
                for param_name, param in sig.parameters.items():
                    if param_name in params:
                        supported_params[param_name] = params[param_name]
                
                # Вызываем функцию с отфильтрованными параметрами
                execution_result = await fn(**supported_params)
                
                # Если команда выполнена, обновляем состояние
                if execution_result.get("success", False):
                    await context.update_state()
                
                # Добавляем результат выполнения
                action_data["execution_result"] = execution_result
            except Exception as e:
                logger.exception(f"Error executing command '{action}': {e}")
                action_data["execution_result"] = {
                    "success": False,
                    "message": f"Ошибка при выполнении команды: {str(e)}"
                }
        else:
            logger.warning(f"No handler for action: {action}")
            action_data["execution_result"] = {
                "success": False,
                "message": f"Неизвестная команда: {action}"
            }
        
        # Добавляем результат в общий список
        results.append(action_data)
    
    # Возвращаем результаты всех команд
    return {
        "multiple_actions": True,
        "actions": results
    }

async def handle_command(text: str) -> Dict[str, Any]:
    """
    Обработать команду от пользователя с использованием контекста презентации.
    
    Args:
        text: Текст команды
        
    Returns:
        Словарь с результатом выполнения команды или команд
    """
    # Получение контекста презентации
    context = PresentationContext()
    await context.update_state()
    
    # Определяем действие из текста с учетом контекста
    result = await identify_action(text, context.state)
    
    # Проверяем, распознано ли несколько действий
    if "multiple_actions" in result and result["multiple_actions"]:
        return await handle_multiple_commands(text, result, context)
    
    # Обработка одиночной команды
    action = result["action"]
    confidence = result["confidence"]
    
    logger.info(f"Identified action: {action} (confidence: {confidence:.2f})")
    
    # Если мы не уверены в действии, запросим уточнение
    if confidence < 0.5 or action == "unknown" or action == "need_clarification":
        logger.warning(f"Low confidence ({confidence:.2f}) for action: {action}")
        
        # Добавляем контекстную информацию в сообщение
        context_hint = context.get_status_message()
        
        result = {
            "action": "need_clarification",
            "confidence": confidence,
            "message": f"Я не уверен, какую команду выполнить. {context_hint}"
        }
        return result
    
    # Проверяем, возможно ли выполнить действие в текущем состоянии
    validation = await context.validate_action(action)
    if not validation["valid"]:
        return {
            "action": action,
            "confidence": confidence,
            "execution_result": {
                "success": False,
                "message": validation["message"]
            }
        }
    
    # Извлекаем параметры из текста для найденного действия
    params = await extract_parameters(text, action)
    
    # Добавляем параметры в результат
    result["params"] = params
    
    # Если функция существует, вызываем её
    if action in COMMAND_FUNCTIONS:
        try:
            # Передаем параметры и контекст в функцию
            fn = COMMAND_FUNCTIONS[action]
            
            # Проверяем подпись функции
            import inspect
            sig = inspect.signature(fn)
            
            # Фильтруем параметры, оставляя только те, которые есть в сигнатуре
            supported_params = {}
            for param_name, param in sig.parameters.items():
                if param_name in params:
                    supported_params[param_name] = params[param_name]
            
            # Вызываем функцию с отфильтрованными параметрами
            execution_result = await fn(**supported_params)
            
            # Если команда выполнена, обновляем состояние
            if execution_result.get("success", False):
                await context.update_state()
            
            # Добавляем результат выполнения в ответ
            result["execution_result"] = execution_result
        except Exception as e:
            logger.exception(f"Error executing command '{action}': {e}")
            result["execution_result"] = {
                "success": False,
                "message": f"Ошибка при выполнении: {str(e)}"
            }
    else:
        logger.warning(f"No handler for action: {action}")
        result["execution_result"] = {
            "success": False,
            "message": f"Неизвестная команда: {action}"
        }
    
    return result

# Добавляем временное хранилище контекста
class DialogContext:
    _instances = {}
    
    @classmethod
    def get_context(cls, user_id: int) -> Dict:
        """
        Получить контекст диалога для пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Контекст диалога
        """
        if user_id not in cls._instances:
            cls._instances[user_id] = {
                "last_action": None,
                "last_message": None,
                "slide_history": [],
                "question_history": [],
                "awaiting_clarification": False,
                "timestamp": None
            }
        return cls._instances[user_id]
    
    @classmethod
    def update_context(cls, user_id: int, **kwargs) -> None:
        """
        Обновить контекст диалога пользователя.
        
        Args:
            user_id: ID пользователя
            **kwargs: Атрибуты для обновления
        """
        ctx = cls.get_context(user_id)
        for key, value in kwargs.items():
            ctx[key] = value
        ctx["timestamp"] = time.time()

async def request_clarification(message_text: str) -> Dict[str, Any]:
    """
    Запрашивает уточнение от пользователя, когда намерение неясно.
    
    Args:
        message_text: Неясный текст пользователя
        
    Returns:
        Словарь с текстом запроса уточнения
    """
    # Запрос уточнения с помощью OpenAI
    system_prompt = """
    Ты - ассистент презентаций. Пользователь отправил сообщение, которое 
    ты не смог точно интерпретировать. Сформулируй вежливый запрос уточнения.
    Предложи 2-3 варианта того, что имел в виду пользователь.
    """
    
    user_prompt = f"""
    Пользователь сказал: "{message_text}"
    
    Я не могу точно определить, что он имел в виду в контексте 
    управления презентацией.
    Сформулируй вежливый запрос уточнения с 2-3 вариантами того, 
    что мог иметь в виду пользователь.
    """
    
    try:
        response = openai.chat.completions.create(
            model="gpt-4-1106-preview",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=150
        )
        
        clarification_text = response.choices[0].message.content
        return {
            "success": True,
            "message": clarification_text
        }
    except Exception as e:
        logger.exception(f"Error generating clarification: {e}")
        return {
            "success": False,
            "message": "Извините, я не совсем понял, что вы имели в виду. "
                      "Можете сформулировать по-другому?"
        }
