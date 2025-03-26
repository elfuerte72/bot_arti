import logging
import aiohttp
from typing import Dict, Any, List, Optional
import random

from config.settings import settings

# Настраиваем логгер
logger = logging.getLogger(__name__)

# API базовый URL
API_BASE_URL = "https://api.tavily.com/v1"


class TavilyAPI:
    """
    Класс для работы с Tavily API для поиска информации в интернете.
    """
    
    @staticmethod
    async def search(
        query: str, 
        search_depth: str = "moderate", 
        max_results: int = 10,
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Выполнить поиск информации по запросу.
        
        Args:
            query: Поисковый запрос
            search_depth: Глубина поиска (basic, moderate, advanced)
            max_results: Максимальное количество результатов
            include_domains: Список доменов для включения
            exclude_domains: Список доменов для исключения
            
        Returns:
            Словарь с результатами поиска
        """
        try:
            # Проверяем наличие ключа API
            if not settings.TAVILY_API_KEY:
                logger.error("Tavily API key is not set")
                return {
                    "success": False,
                    "error": "Ключ API Tavily не настроен"
                }
            
            url = f"{API_BASE_URL}/search"
            
            payload = {
                "api_key": settings.TAVILY_API_KEY,
                "query": query,
                "search_depth": search_depth,
                "max_results": max_results
            }
            
            # Добавляем опциональные параметры, если они указаны
            if include_domains:
                payload["include_domains"] = include_domains
            if exclude_domains:
                payload["exclude_domains"] = exclude_domains
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        logger.error(
                            f"Tavily API error: {response.status}, "
                            f"{await response.text()}"
                        )
                        return {
                            "success": False,
                            "error": f"API вернул статус {response.status}"
                        }
                    
                    data = await response.json()
                    return {
                        "success": True,
                        "results": data.get("results", []),
                        "query": query,
                        "content": data.get("answer", "")
                    }
        
        except aiohttp.ClientError as e:
            logger.exception(f"Ошибка сетевого запроса к Tavily API: {e}")
            return {
                "success": False,
                "error": f"Ошибка сетевого запроса: {str(e)}"
            }
        except Exception as e:
            error_msg = f"Непредвиденная ошибка при запросе к Tavily API: {e}"
            logger.exception(error_msg)
            return {
                "success": False,
                "error": f"Непредвиденная ошибка: {str(e)}"
            }
    
    @staticmethod
    async def format_search_results(search_data: Dict[str, Any]) -> str:
        """
        Форматирует результаты поиска в читаемый текст.
        
        Args:
            search_data: Результаты поиска от Tavily API
            
        Returns:
            Отформатированный текст результатов
        """
        if not search_data.get("success", False):
            return (
                f"К сожалению, не получилось найти информацию. "
                f"{search_data.get('error', 'Возникла проблема при поиске')}"
            )
        
        results = search_data.get("results", [])
        content = search_data.get("content", "")
        query = search_data.get("query", "")
        
        intro_phrases = [
            f"Так, я поискал информацию о '{query}'. Вот что нашел.",
            f"Отлично! По запросу '{query}' я нашел интересную информацию.",
            f"По вашему вопросу о '{query}' есть следующая информация.",
            f"Давайте разберемся с '{query}'. Я нашел следующее."
        ]
        
        # Выбираем случайную фразу для начала
        intro = random.choice(intro_phrases)
        
        if content:
            formatted_text = f"{intro}\n\n{content}\n\n"
        else:
            formatted_text = f"{intro}\n\n"
        
        # Добавляем результаты, если они есть
        if results:
            formatted_text += "Я также нашел несколько полезных источников:\n"
            # Ограничиваем до 3 результатов
            for i, result in enumerate(results[:3], 1):
                title = result.get("title", "Без названия")
                url = result.get("url", "#")
                formatted_text += f"{i}. {title}\n   {url}\n\n"
        else:
            formatted_text += (
                "Хотя конкретных источников я не нашел, надеюсь, "
                "эта информация вам поможет."
            )
        
        return formatted_text 