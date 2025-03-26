import re
from typing import Dict, Any, List, Tuple, Optional

# Шаблоны для распознавания команд с параметрами
COMMAND_PATTERNS = [
    # Переход к слайду по номеру
    (r"(покажи|перейди|открой|слайд)\s+(на\s+)?(слайд\s+)?(\d+)", "goto_slide", lambda m: {"slide_number": int(m.group(4))}),
    
    # Переход к слайду по названию/содержанию
    (r"(покажи|перейди|открой)\s+(на\s+)?(слайд\s+)?(про|о|об)\s+(.+)", "goto_slide", lambda m: {"slide_title": m.group(5)}),
    
    # Распознавание раздела вида "4. Здоровье"
    (r"(\d+)[\.\s-]+(\w+)", "goto_slide", lambda m: {"slide_title": f"{m.group(1)}. {m.group(2)}"}),
    
    # Запуск презентации
    (r"(начать|начни|запусти|старт|запустить)\s+(презентацию|показ)", "start", lambda m: {}),
    
    # Переход к следующему слайду
    (r"(дальше|вперед|следующий|далее)", "next_slide", lambda m: {}),
    
    # Переход к предыдущему слайду
    (r"(назад|предыдущий|вернись)", "previous_slide", lambda m: {}),
    
    # Озвучивание текста
    (r"(скажи|прочитай|озвучь|читай)", "speak_next_block", lambda m: {}),
]

def parse_natural_command(text: str) -> Optional[Dict[str, Any]]:
    """
    Распознает команду на естественном языке и извлекает параметры.
    
    Args:
        text: Текст команды от пользователя
        
    Returns:
        Словарь с распознанной командой и параметрами или None
    """
    text = text.lower().strip()
    
    for pattern, action, param_extractor in COMMAND_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            params = param_extractor(match)
            return {
                "action": action,
                "params": params,
                "confidence": 0.9,  # Высокая уверенность для точного совпадения
                "matched_text": match.group(0)
            }
    
    # Если не найдено точное соответствие, попробуем нечеткий поиск
    return fuzzy_match_command(text) 