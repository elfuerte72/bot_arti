from enum import Enum
from typing import Dict, Any, Optional

class BotState(Enum):
    IDLE = "idle"                   # Ожидание команды
    WAITING_FOR_KEYNOTE = "waiting_for_keynote"  # Ожидаем запуска Keynote
    WAITING_FOR_PRESENTATION = "waiting_for_presentation"  # Ожидаем открытия презентации
    PRESENTING = "presenting"        # Идет презентация
    SEARCHING_SLIDE = "searching_slide"  # Ищем конкретный слайд
    ANSWERING_QUESTION = "answering_question"  # Отвечаем на вопрос

class UserSession:
    """Класс для хранения сессии пользователя и состояния диалога"""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.state = BotState.IDLE
        self.context = {}  # Дополнительный контекст сессии
        self.last_command = None
        self.last_slide_text = None
    
    def update_state(self, new_state: BotState) -> None:
        """Обновляет состояние бота для пользователя"""
        self.state = new_state
    
    def set_context(self, key: str, value: Any) -> None:
        """Сохраняет значение в контексте сессии"""
        self.context[key] = value
    
    def get_context(self, key: str, default: Any = None) -> Any:
        """Получает значение из контекста сессии"""
        return self.context.get(key, default)

# Глобальное хранилище сессий пользователей
user_sessions: Dict[int, UserSession] = {}

def get_user_session(user_id: int) -> UserSession:
    """Получает или создает сессию пользователя"""
    if user_id not in user_sessions:
        user_sessions[user_id] = UserSession(user_id)
    return user_sessions[user_id] 