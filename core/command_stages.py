from typing import Dict, Any, List, Callable, Awaitable
import logging

logger = logging.getLogger(__name__)

# Тип для функций-обработчиков этапов
StageHandler = Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]

# Структура для хранения многоэтапных сценариев
COMMAND_FLOWS: Dict[str, Dict[int, StageHandler]] = {}

def register_flow(command: str, stage: int, handler: StageHandler) -> None:
    """
    Регистрирует обработчик для определенного этапа команды.
    
    Args:
        command: Название команды
        stage: Номер этапа (начиная с 0)
        handler: Асинхронная функция-обработчик
    """
    if command not in COMMAND_FLOWS:
        COMMAND_FLOWS[command] = {}
    
    COMMAND_FLOWS[command][stage] = handler

async def execute_flow_stage(command: str, stage: int, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Выполняет определенный этап многоэтапного сценария.
    
    Args:
        command: Название команды
        stage: Номер этапа
        data: Данные для обработки
        
    Returns:
        Результат обработки этапа с указанием следующего этапа или завершения
    """
    if command not in COMMAND_FLOWS or stage not in COMMAND_FLOWS[command]:
        return {
            "success": False,
            "message": f"Неизвестный этап {stage} для команды {command}",
            "is_complete": True
        }
    
    try:
        # Получаем и выполняем обработчик этапа
        handler = COMMAND_FLOWS[command][stage]
        result = await handler(data)
        
        # Если обработчик не вернул признак завершения, считаем что это не последний этап
        if "is_complete" not in result:
            result["is_complete"] = False
        
        # Если это не последний этап, указываем следующий
        if not result["is_complete"] and "next_stage" not in result:
            result["next_stage"] = stage + 1
        
        return result
    except Exception as e:
        logger.exception(f"Ошибка при выполнении этапа {stage} команды {command}: {e}")
        return {
            "success": False,
            "message": f"Ошибка обработки: {str(e)}",
            "is_complete": True
        } 