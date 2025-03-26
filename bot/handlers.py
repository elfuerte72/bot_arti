import os
import uuid
import logging

from aiogram import Router, F
from aiogram.types import Message, FSInputFile, CallbackQuery
from aiogram.enums import ChatAction
from aiogram.filters import Command

from config.settings import settings
from core.command_router import handle_command
from core.user_session import get_user_session
from voice.speech_to_text import process_voice_message
from voice.text_to_speech import synthesize_response

# Настраиваем логгер
logger = logging.getLogger(__name__)

# Create routers
router = Router()
cmd_router = Router()


@cmd_router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """Handle /start command."""
    start_text = (
        "Привет! Я помогу управлять презентацией. "
        "Говори команды вроде 'следующий слайд', 'начать' или задавай вопросы."
    )
    await message.answer(start_text)
    
    # Озвучиваем приветствие
    try:
        voice_text = "Привет! Я бот для управления презентациями. Чем помочь?"
        voice_response = await synthesize_response(voice_text)
        voice_file = FSInputFile(voice_response)
        await message.answer_voice(voice_file)
        os.remove(voice_response)
    except Exception as e:
        logger.exception(f"Error synthesizing start message: {e}")


@cmd_router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Handle /help command."""
    help_text = (
        "Основные команды:\n"
        "- следующий/предыдущий слайд\n"
        "- начать/завершить презентацию\n"
        "- говори/повтори текст\n"
        "- ответь на вопрос\n"
        "- поиск информации"
    )
    await message.answer(help_text)
    
    # Озвучиваем справку
    try:
        voice_text = (
            "Я управляю презентацией: переключаю слайды, озвучиваю текст, "
            "отвечаю на вопросы и могу искать информацию."
        )
        voice_response = await synthesize_response(voice_text)
        voice_file = FSInputFile(voice_response)
        await message.answer_voice(voice_file)
        os.remove(voice_response)
    except Exception as e:
        logger.exception(f"Error synthesizing help message: {e}")


@router.message(F.voice)
async def voice_message_handler(message: Message) -> None:
    """
    Handle voice messages from the user.
    
    Download, save to a temp file, and pass to the STT service.
    """
    # Индикатор обработки
    processing_msg = await message.answer("Обрабатываю...")
    
    # Create unique file name for voice message
    voice_file_name = f"{uuid.uuid4()}.ogg"
    voice_file_path = settings.VOICE_TEMP_PATH / voice_file_name
    
    try:
        # Download voice message
        await message.bot.download(
            message.voice,
            destination=voice_file_path
        )
        
        # Process voice with STT
        try:
            text = await process_voice_message(voice_file_path)
        except Exception as e:
            await message.reply(f"Ошибка распознавания: {str(e)}")
            await processing_msg.delete()
            return

        # Добавляем лог для отладки распознавания
        logger.info(f"Распознан текст: {text}")
        
        # Обрабатываем команду и получаем результат
        result = await handle_command(text)
        
        # Delete processing message
        await processing_msg.delete()
        
        # Проверяем наличие множественных команд
        if "multiple_actions" in result and result["multiple_actions"]:
            actions = result.get("actions", [])
            
            # Форматируем ответ
            response_parts = []
            voice_parts = []
            
            for action_data in actions:
                if "execution_result" in action_data:
                    exec_result = action_data["execution_result"]
                    
                    if exec_result["success"]:
                        # Берем только основной текст
                        action_text = exec_result.get(
                            "text_to_speak", 
                            exec_result["message"]
                        )
                        voice_text = action_text
                    else:
                        action_text = exec_result["message"]
                        voice_text = action_text
                    
                    response_parts.append(action_text)
                    voice_parts.append(voice_text)
                else:
                    action = action_data["action"]
                    action_text = f"Выполняю {action}"
                    response_parts.append(action_text)
                    voice_parts.append(action_text)
            
            # Отправляем краткий ответ
            if response_parts:
                await message.reply(". ".join(response_parts))
                
                # Озвучиваем ответы
                try:
                    voice_text = ". ".join(voice_parts)
                    voice_response = await synthesize_response(voice_text)
                    voice_file = FSInputFile(voice_response)
                    await message.answer_voice(voice_file)
                    os.remove(voice_response)
                except Exception as e:
                    logger.exception(f"Error synthesizing voice response: {e}")
            
            return
        
        # Отправляем ответ для одиночной команды
        if "execution_result" in result:
            exec_result = result["execution_result"]
            
            if exec_result["success"]:
                # Используем прямой ответ без лишних деталей, предпочитая text_to_speak
                response_text = exec_result.get(
                    "text_to_speak", 
                    exec_result["message"]
                )
            else:
                response_text = exec_result["message"]
            
            await message.reply(response_text)
            
            # Special handling for speak_next_block and repeat_last_block
            if (result["action"] in ["speak_next_block", "repeat_last_block"] 
                    and exec_result["success"] 
                    and "text_to_speak" in exec_result):
                try:
                    # Получаем скорость из параметров или используем по умолчанию
                    rate = 0.9
                    if "params" in result and "rate" in result["params"]:
                        rate = result["params"]["rate"]
                    
                    # Синтезируем текст со слайда
                    voice_response = await synthesize_response(
                        exec_result["text_to_speak"],
                        rate=rate
                    )
                    
                    # Send voice message
                    voice_file = FSInputFile(voice_response)
                    await message.answer_voice(voice_file)
                    
                    # Cleanup voice file
                    os.remove(voice_response)
                except Exception as e:
                    logger.exception(f"Error synthesizing slide text: {e}")
                    await message.answer("Не удалось озвучить текст")
            # Озвучиваем все успешные команды
            elif exec_result["success"]:
                try:
                    voice_response = await synthesize_response(response_text)
                    voice_file = FSInputFile(voice_response)
                    await message.answer_voice(voice_file)
                    os.remove(voice_response)
                except Exception as e:
                    logger.exception(f"Error synthesizing response: {e}")
        else:
            # Используем действие или настраиваемый ответ
            response_text = ""
            
            # Если у нас есть сообщение об уточнении, используем его
            if result["action"] == "need_clarification" and "message" in result:
                response_text = result["message"]
            # Иначе используем стандартное сообщение о действии
            else:
                response_text = f"Выполняю {result['action']}"
            
            await message.reply(response_text)
            
            # Озвучиваем ответ
            try:
                voice_response = await synthesize_response(response_text)
                voice_file = FSInputFile(voice_response)
                await message.answer_voice(voice_file)
                os.remove(voice_response)
            except Exception as e:
                logger.exception(f"Error synthesizing response: {e}")
    
    except Exception as e:
        logger.exception(f"Error processing voice message: {e}")
        await processing_msg.delete()
        err_msg = f"Ошибка при обработке сообщения: {str(e)}"
        await message.reply(err_msg)
    
    finally:
        # Clean up the temporary file
        if os.path.exists(voice_file_path):
            try:
                os.remove(voice_file_path)
            except Exception as e:
                logger.error(f"Error removing temporary file: {e}")


@router.message(F.text)
async def text_message_handler(message: Message) -> None:
    """Handle text messages and process as commands."""
    # Показываем пользователю, что бот обрабатывает сообщение
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    
    # Получаем контекст диалога и сессию пользователя
    user_session = get_user_session(message.from_user.id)
    
    # Если ожидаем уточнения, обрабатываем ответ по-особому
    if user_session["awaiting_clarification"]:
        # Сбрасываем флаг ожидания уточнения
        user_session["awaiting_clarification"] = False
        # Дополнительная обработка уточнения может быть здесь
    
    # Process the command
    result = await handle_command(message.text)
    
    # Если нужно уточнение
    if result["action"] == "need_clarification":
        clarification_msg = result.get("message", "Не совсем понял, что вы имеете в виду. Можете уточнить?")
        await message.reply(clarification_msg)
        
        # Озвучиваем запрос уточнения
        try:
            voice_response = await synthesize_response(
                clarification_msg
            )
            voice_file = FSInputFile(voice_response)
            await message.answer_voice(voice_file)
            os.remove(voice_response)
        except Exception as e:
            logger.exception(f"Error synthesizing clarification: {e}")
        
        # Обновляем контекст
        user_session["awaiting_clarification"] = True
        user_session["last_message"] = message.text
        return
    
    # Проверяем, содержит ли результат несколько команд
    if "multiple_actions" in result and result["multiple_actions"]:
        # Обновляем контекст диалога с последним действием
        actions = result.get("actions", [])
        if actions:
            last_action = actions[-1]["action"]
            user_session["last_action"] = last_action
            user_session["last_message"] = message.text
        
        # Формируем общий ответ для всех команд
        response_parts = []
        voice_parts = []
        
        for action_data in actions:
            if "execution_result" in action_data:
                exec_result = action_data["execution_result"]
                
                if exec_result["success"]:
                    # Берем только основной текст без форматирования
                    response_text = exec_result.get(
                        "text_to_speak", 
                        exec_result["message"]
                    )
                    voice_text = response_text
                else:
                    response_text = exec_result["message"]
                    voice_text = response_text
                
                # Добавляем в общий ответ
                response_parts.append(response_text)
                voice_parts.append(voice_text)
            else:
                action = action_data["action"]
                action_text = f"Выполняю {action}"
                response_parts.append(action_text)
                voice_parts.append(action_text)
        
        # Отправляем объединенный ответ
        if response_parts:
            await message.reply(". ".join(response_parts))
            
            # Озвучиваем ответ
            try:
                voice_text = ". ".join(voice_parts)
                voice_response = await synthesize_response(voice_text)
                voice_file = FSInputFile(voice_response)
                await message.answer_voice(voice_file)
                os.remove(voice_response)
            except Exception as e:
                logger.exception(f"Error synthesizing response: {e}")
        
        return
    
    # Обновляем контекст диалога
    user_session["last_action"] = result["action"]
    user_session["last_message"] = message.text
    
    # Отправляем ответ для одиночной команды
    if "execution_result" in result:
        exec_result = result["execution_result"]
        
        if exec_result["success"]:
            # Используем текст для озвучивания, если есть, или сообщение
            response_text = exec_result.get(
                "text_to_speak", 
                exec_result["message"]
            )
        else:
            response_text = exec_result["message"]
        
        await message.reply(response_text)
        
        # Special handling for speak_next_block and repeat_last_block
        if (result["action"] in ["speak_next_block", "repeat_last_block"] 
                and exec_result["success"] 
                and "text_to_speak" in exec_result):
            try:
                # Получаем скорость из параметров или используем по умолчанию
                rate = 0.9
                if "params" in result and "rate" in result["params"]:
                    rate = result["params"]["rate"]
                
                # Синтезируем текст со слайда
                voice_response = await synthesize_response(
                    exec_result["text_to_speak"],
                    rate=rate
                )
                
                # Send voice message
                voice_file = FSInputFile(voice_response)
                await message.answer_voice(voice_file)
                
                # Cleanup voice file
                os.remove(voice_response)
            except Exception as e:
                logger.exception(f"Error synthesizing slide text: {e}")
                await message.answer("Не удалось озвучить текст")
        # Озвучиваем все успешные команды
        elif exec_result["success"]:
            try:
                voice_response = await synthesize_response(response_text)
                voice_file = FSInputFile(voice_response)
                await message.answer_voice(voice_file)
                os.remove(voice_response)
            except Exception as e:
                logger.exception(f"Error synthesizing response: {e}")
    else:
        # Используем действие или настраиваемый ответ
        response_text = ""
        
        # Если у нас есть сообщение об уточнении, используем его
        if result["action"] == "need_clarification" and "message" in result:
            response_text = result["message"]
        # Иначе используем стандартное сообщение о действии
        else:
            response_text = f"Выполняю {result['action']}"
        
        await message.reply(response_text)
        
        # Озвучиваем ответ
        try:
            voice_response = await synthesize_response(response_text)
            voice_file = FSInputFile(voice_response)
            await message.answer_voice(voice_file)
            os.remove(voice_response)
        except Exception as e:
            logger.exception(f"Error synthesizing response: {e}")


@router.callback_query()
async def callback_handler(query: CallbackQuery) -> None:
    """Обработка нажатий на кнопки клавиатуры"""
    # Подтверждаем получение запроса для мгновенной обратной связи
    await query.answer()
    
    # Обновляем интерфейс, добавляя emoji-реакцию к сообщению
    if query.message:
        # Показываем реакцию в интерфейсе
        emoji_map = {
            "next_slide": "➡️",
            "prev_slide": "⬅️",
            "pause": "⏸",
            "resume": "▶️",
            "speak_next_block": "🔊",
            "end_presentation": "🛑"
        }
        
        action = query.data
        if action in emoji_map:
            try:
                # Добавляем соответствующую реакцию на сообщение
                await query.message.react([emoji_map[action]])
            except Exception as e:
                logger.exception(f"Ошибка при добавлении реакции: {e}")
