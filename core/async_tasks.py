import asyncio
from functools import wraps
from typing import Callable, Any, Dict

def async_task(f):
    """Декоратор для выполнения функции в отдельной задаче"""
    @wraps(f)
    async def wrapper(*args, **kwargs):
        return await asyncio.create_task(f(*args, **kwargs))
    return wrapper

@async_task
async def process_long_running_command(command: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Обработка длительных команд в отдельной задаче"""
    # Долгая обработка...
    await asyncio.sleep(1)  # Имитация длительной операции
    
    # Возвращаем результат
    return {
        "success": True,
        "message": "Операция выполнена успешно",
        "data": {}
    } 