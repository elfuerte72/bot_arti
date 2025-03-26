from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

def get_presentation_controls() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру с основными элементами управления презентацией"""
    keyboard = InlineKeyboardMarkup(row_width=3)
    
    # Кнопки управления слайдами
    prev_button = InlineKeyboardButton("⬅️ Назад", callback_data="prev_slide")
    pause_button = InlineKeyboardButton("⏸ Пауза", callback_data="pause")
    next_button = InlineKeyboardButton("➡️ Далее", callback_data="next_slide")
    
    # Дополнительные кнопки
    speak_button = InlineKeyboardButton("🔊 Озвучить", callback_data="speak_next_block")
    end_button = InlineKeyboardButton("🛑 Завершить", callback_data="end_presentation")
    
    # Добавляем кнопки на клавиатуру
    keyboard.row(prev_button, pause_button, next_button)
    keyboard.row(speak_button, end_button)
    
    return keyboard

def get_slide_navigation() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру для навигации по слайдам"""
    keyboard = InlineKeyboardMarkup(row_width=5)
    
    # Создаем кнопки для перехода к конкретным слайдам (примерно первые 10)
    for i in range(1, 11):
        keyboard.insert(InlineKeyboardButton(str(i), callback_data=f"goto_slide_{i}"))
    
    # Кнопка для ввода произвольного номера слайда
    custom_button = InlineKeyboardButton("Другой слайд...", callback_data="custom_slide")
    keyboard.row(custom_button)
    
    return keyboard 