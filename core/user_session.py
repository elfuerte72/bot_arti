from typing import Dict, Any

# Хранилище сессий пользователей
_user_sessions: Dict[int, Dict[str, Any]] = {}

def get_user_session(user_id: int) -> Dict[str, Any]:
    """
    Получить или создать сессию пользователя.
    
    Args:
        user_id: ID пользователя в Telegram
        
    Returns:
        Dict с данными сессии пользователя
    """
    if user_id not in _user_sessions:
        _user_sessions[user_id] = {
            "last_command": None,
            "last_response": None,
            "context": {},
            "voice_settings": {
                "rate": 1.0,
                "volume": 1.0
            },
            "awaiting_clarification": False,
            "last_message": None
        }
    return _user_sessions[user_id] 