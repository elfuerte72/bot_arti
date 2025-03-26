import time
from typing import Dict, Any, Optional, List

# Кэш для хранения структуры презентации
PRESENTATION_CACHE = {
    "data": None,
    "timestamp": 0,
    "ttl": 30  # Время жизни кэша в секундах
}

async def get_cached_presentation_structure() -> Optional[Dict[str, Any]]:
    """
    Получает структуру презентации из кэша или обновляет ее.
    
    Returns:
        Структура презентации или None при ошибке
    """
    current_time = time.time()
    
    # Проверяем, нужно ли обновить кэш
    if (PRESENTATION_CACHE["data"] is None or 
            current_time - PRESENTATION_CACHE["timestamp"] > PRESENTATION_CACHE["ttl"]):
        # Получаем свежие данные
        from slides.keynote_integration import get_presentation_structure
        data = await get_presentation_structure()
        
        if data:
            # Обновляем кэш
            PRESENTATION_CACHE["data"] = data
            PRESENTATION_CACHE["timestamp"] = current_time
    
    return PRESENTATION_CACHE["data"]

async def find_slide_by_content(search_text: str) -> Optional[int]:
    """
    Ищет слайд по содержимому или названию.
    
    Args:
        search_text: Текст для поиска
        
    Returns:
        Номер слайда или None, если не найден
    """
    # Получаем структуру презентации
    presentation = await get_cached_presentation_structure()
    
    if not presentation or "slides" not in presentation:
        return None
    
    # Поиск по слайдам
    search_text = search_text.lower()
    best_match = None
    best_score = 0
    
    for slide_info in presentation["slides"]:
        title = slide_info.get("title", "").lower()
        body = slide_info.get("body", "").lower()
        
        # Проверяем точное совпадение в заголовке
        if search_text in title:
            score = len(search_text) / len(title) * 100 if len(title) > 0 else 0
            if score > best_score:
                best_score = score
                best_match = slide_info["slide_num"]
        
        # Проверяем совпадение в тексте слайда
        elif search_text in body:
            score = len(search_text) / len(body) * 50 if len(body) > 0 else 0
            if score > best_score:
                best_score = score
                best_match = slide_info["slide_num"]
    
    return best_match 