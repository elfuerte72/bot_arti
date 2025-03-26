import logging
from typing import Dict, Any, Optional

from openai import AsyncOpenAI

from config.settings import settings
from core.tavily_search import TavilyAPI
from core.system_prompts import get_system_prompt

# Настраиваем логгер
logger = logging.getLogger(__name__)

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


async def analyze_text(text: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Анализирует текст с помощью GPT и возвращает структурированный ответ с действием и ответом.
    
    Args:
        text: Текст для анализа
        context: Дополнительный контекст для промпта (опционально)
        
    Returns:
        Структурированный ответ с полями action, params и response
    """
    try:
        # Получаем системный промпт в стиле JARVIS с контекстом
        system_prompt = get_system_prompt(context)
        
        # Готовим запрос к API
        client = await get_openai_client()
        response = await client.chat.completions.create(
            model="gpt-4-turbo-preview",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        # Извлекаем ответ
        try:
            import json
            response_text = response.choices[0].message.content
            structured_response = json.loads(response_text)
            
            # Проверяем наличие всех необходимых полей
            if "action" not in structured_response:
                structured_response["action"] = "unknown"
            
            if "params" not in structured_response:
                structured_response["params"] = {}
                
            if "response" not in structured_response:
                structured_response["response"] = "Я не совсем понял, что вы хотите. Могли бы вы уточнить?"
            
            # Преобразуем действия в совместимый формат
            # Маппинг действий из нового промпта в старые имена действий
            action_mapping = {
                "start_presentation": "start",
                "stop": "pause",
                "generate_answer": "handle_question",
                "explain_simpler": "speak_next_block",
                "summarize": "generate_summary",
                "unknown": "need_clarification"
            }
            
            # Применяем маппинг, если нужно
            if structured_response["action"] in action_mapping:
                structured_response["action"] = action_mapping[structured_response["action"]]
            
            # Добавляем уровень уверенности для совместимости
            structured_response["confidence"] = 0.9
                
            return structured_response
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Ошибка при разборе ответа OpenAI: {e}")
            return {
                "action": "need_clarification",
                "params": {},
                "response": "Произошла ошибка при обработке вашего запроса. Повторите, пожалуйста.",
                "confidence": 0.3
            }
            
    except Exception as e:
        logger.exception(f"Ошибка при обращении к OpenAI API: {e}")
        return {
            "action": "need_clarification",
            "params": {},
            "response": f"Не удалось обработать запрос: {str(e)}",
            "confidence": 0.3
        }


class QuestionHandler:
    """
    Обработчик вопросов с использованием GPT-4 и поиска информации.
    """
    
    @staticmethod
    async def search_and_process_question(
        question: str, 
        search_enabled: bool = True,
        search_depth: str = "moderate"
    ) -> Dict[str, Any]:
        """
        Обработать вопрос с использованием поиска информации и GPT-4.
        
        Args:
            question: Текст вопроса
            search_enabled: Включить поиск информации
            search_depth: Глубина поиска
            
        Returns:
            Словарь с ответом и дополнительной информацией
        """
        try:
            search_results = None
            
            # Выполняем поиск информации, если он включен
            if search_enabled:
                search_results = await TavilyAPI.search(
                    query=question,
                    search_depth=search_depth
                )
            
            # Получаем ответ от GPT-4
            answer = await QuestionHandler.generate_answer(
                question=question,
                search_results=search_results
            )
            
            return {
                "success": True,
                "question": question,
                "answer": answer,
                "search_results": search_results
            }
            
        except Exception as e:
            logger.exception(f"Ошибка при обработке вопроса: {e}")
            return {
                "success": False,
                "error": f"Не удалось обработать вопрос: {str(e)}"
            }
    
    @staticmethod
    async def generate_answer(
        question: str,
        search_results: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Генерировать ответ на вопрос с использованием GPT-4.
        
        Args:
            question: Текст вопроса
            search_results: Результаты поиска (опционально)
            
        Returns:
            Текст ответа
        """
        try:
            # Подготавливаем контекст для запроса
            system_prompt = """
            Ты - дружелюбный и отзывчивый ассистент для проведения презентаций.
            Твоя задача - отвечать на вопросы простым разговорным языком.
            Твой характер: терпеливый, внимательный и слегка неформальный.
            Используй разговорные обороты, показывай заинтересованность в теме.
            Начинай свои ответы с приветливых фраз, например: "Конечно", "Хороший вопрос", 
            "Давай разберемся", "Интересный момент".
            Иногда добавляй вводные фразы: "Как я понимаю", "Насколько я знаю".
            Используй предоставленную контекстную информацию, если она доступна.
            Говори как живой человек, избегай формальностей, символов и эмодзи.
            Если информации недостаточно, скажи об этом простым языком и предложи, 
            что можно уточнить.
            """
            
            # Создаем сообщения для запроса
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Вопрос: {question}"}
            ]
            
            # Если есть результаты поиска, добавляем их в контекст
            if search_results and search_results.get("success", False):
                search_context = ""
                
                # Добавляем полученный ответ, если он есть
                content = search_results.get("content", "")
                if content:
                    search_context += f"Информация по запросу:\n{content}\n\n"
                
                # Добавляем результаты поиска
                results = search_results.get("results", [])
                if results:
                    search_context += "Дополнительные источники:\n"
                    for i, result in enumerate(results[:3], 1):
                        title = result.get("title", "")
                        snippet = result.get("content", "")
                        search_context += f"{i}. {title}\n{snippet}\n\n"
                
                # Добавляем контекст в сообщения
                if search_context:
                    content_msg = (
                        f"Вот информация, найденная в Интернете:"
                        f"\n\n{search_context}"
                    )
                    messages.append({
                        "role": "user", 
                        "content": content_msg
                    })
            
            # Запрос к API
            client = await get_openai_client()
            response = await client.chat.completions.create(
                model="gpt-4-turbo", 
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.exception(f"Ошибка при генерации ответа: {e}")
            return f"Ошибка при генерации ответа: {str(e)}"
    
    @staticmethod
    async def format_answer(answer_data: Dict[str, Any]) -> str:
        """
        Форматирует данные ответа в читаемый текст.
        
        Args:
            answer_data: Данные ответа
            
        Returns:
            Отформатированный текст ответа
        """
        if not answer_data.get("success", False):
            error_msg = answer_data.get('error', 'неизвестная ошибка')
            return f"К сожалению, не могу дать ответ: {error_msg}"
        
        answer = answer_data.get("answer", "")
        
        return answer 