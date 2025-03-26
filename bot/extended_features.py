from aiogram import Bot
from aiogram.types import WebAppInfo, MenuButtonWebApp
from typing import Optional

async def set_menu_button(bot: Bot, chat_id: int, text: str, url: str) -> bool:
    """
    Устанавливает кнопку меню бота с веб-приложением.
    
    Args:
        bot: Экземпляр бота
        chat_id: ID чата
        text: Текст кнопки
        url: URL веб-приложения
        
    Returns:
        True при успешной установке
    """
    try:
        # Создаем веб-приложение
        web_app = WebAppInfo(url=url)
        
        # Устанавливаем кнопку меню
        await bot.set_chat_menu_button(
            chat_id=chat_id,
            menu_button=MenuButtonWebApp(text=text, web_app=web_app)
        )
        return True
    except Exception as e:
        logger.exception(f"Ошибка установки кнопки меню: {e}")
        return False

async def show_presentation_controls(bot: Bot, chat_id: int) -> None:
    """
    Показывает встроенную клавиатуру для управления презентацией.
    
    Args:
        bot: Экземпляр бота
        chat_id: ID чата
    """
    # Получаем клавиатуру управления
    keyboard = get_presentation_controls()
    
    # Отправляем сообщение с клавиатурой
    await bot.send_message(
        chat_id=chat_id,
        text="Управление презентацией:",
        reply_markup=keyboard
    ) 