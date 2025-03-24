import os
import uuid
import logging

from aiogram import Router, F
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command

from config.settings import settings
from core.command_router import handle_command
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
    await message.answer(
        "Привет! Я бот для управления презентациями. "
        "Отправляй мне текстовые или голосовые команды "
        "для управления слайдами.\n\n"
        "Примеры команд: 'следующий слайд', 'назад', 'начать презентацию'."
    )


@cmd_router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Handle /help command."""
    help_text = (
        "📝 <b>Текстовые команды:</b>\n"
        "- следующий слайд\n"
        "- предыдущий слайд\n"
        "- пауза\n"
        "- продолжить\n"
        "- начать презентацию\n"
        "- завершить презентацию\n"
        "- статус\n"
        "- говори/читай (озвучить следующий блок текста)\n"
        "- повтори (повторить последний блок)\n"
        "- ответь на вопрос: [текст вопроса]\n\n"
        "🎤 <b>Голосовые команды:</b>\n"
        "Вы также можете отправить голосовое сообщение с любой из команд выше."
    )
    await message.answer(help_text, parse_mode="HTML")


@router.message(F.voice)
async def voice_message_handler(message: Message) -> None:
    """
    Handle voice messages from the user.
    
    Download, save to a temp file, and pass to the STT service.
    """
    # Индикатор обработки
    processing_msg = await message.answer("🎧 Обрабатываю голосовое сообщение...")
    
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
            await message.reply(f"❌ Ошибка распознавания: {str(e)}")
            await processing_msg.delete()
            return

        # Process the command
        result = await handle_command(text)
        
        # Prepare response text
        response_text = f"🎙️ Распознано: \"{text}\"\n\n"
        
        # Add execution details if available
        if "execution_result" in result:
            exec_result = result["execution_result"]
            if exec_result["success"]:
                response_text += f"✅ {exec_result['message']}"
            else:
                response_text += f"❌ {exec_result['message']}"
        else:
            response_text += (
                f"Команда: {result['action']} "
                f"(уверенность: {result['confidence']:.2f})"
            )
        
        # Delete processing message
        await processing_msg.delete()
        
        # Reply with text response
        await message.reply(response_text)
        
        # Generate voice response for most commands
        if (result["confidence"] > 0.8 and "execution_result" in result):
            exec_result = result["execution_result"]
            
            # Special handling for speak_next_block and repeat_last_block
            if (result["action"] in ["speak_next_block", "repeat_last_block"] and 
                    exec_result["success"] and "text_to_speak" in exec_result):
                try:
                    # Синтезируем текст со слайда
                    voice_response = await synthesize_response(
                        exec_result["text_to_speak"],
                        rate=0.9  # Немного медленнее для лучшего понимания
                    )
                    
                    # Send voice message
                    voice_file = FSInputFile(voice_response)
                    await message.answer_voice(voice_file)
                    
                    # Cleanup voice file
                    os.remove(voice_response)
                except Exception as e:
                    logger.exception(f"Error synthesizing slide text: {e}")
                    await message.answer(
                        "Не удалось синтезировать речь для текста слайда"
                    )
            # Standard response for other commands
            elif exec_result["success"]:
                try:
                    voice_response = await synthesize_response(
                        exec_result["message"]
                    )
                    
                    # Send voice message
                    voice_file = FSInputFile(voice_response)
                    await message.answer_voice(voice_file)
                    
                    # Cleanup voice file
                    os.remove(voice_response)
                except Exception as e:
                    logger.exception(f"Error synthesizing response: {e}")
    
    except Exception as e:
        logger.exception(f"Error processing voice message: {e}")
        await processing_msg.delete()
        await message.reply(f"❌ Произошла ошибка при обработке сообщения: {str(e)}")
    
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
    # Process the command
    result = await handle_command(message.text)
    
    # If command is recognized with sufficient confidence
    if result["confidence"] > 0.7:
        # Prepare response based on execution result
        if "execution_result" in result:
            exec_result = result["execution_result"]
            
            if exec_result["success"]:
                response_text = f"✅ {exec_result['message']}"
            else:
                response_text = f"❌ {exec_result['message']}"
            
            await message.reply(response_text)
            
            # Special handling for speak_next_block and repeat_last_block
            if (result["action"] in ["speak_next_block", "repeat_last_block"] and 
                    exec_result["success"] and "text_to_speak" in exec_result):
                try:
                    # Синтезируем текст со слайда
                    voice_response = await synthesize_response(
                        exec_result["text_to_speak"],
                        rate=0.9  # Немного медленнее для лучшего понимания
                    )
                    
                    # Send voice message
                    voice_file = FSInputFile(voice_response)
                    await message.answer_voice(voice_file)
                    
                    # Cleanup voice file
                    os.remove(voice_response)
                except Exception as e:
                    logger.exception(f"Error synthesizing slide text: {e}")
                    await message.answer(
                        "Не удалось синтезировать речь для текста слайда"
                    )
            # Optional voice response for successful commands
            elif exec_result["success"] and result["confidence"] > 0.85:
                try:
                    voice_response = await synthesize_response(
                        exec_result["message"]
                    )
                    voice_file = FSInputFile(voice_response)
                    await message.answer_voice(voice_file)
                    os.remove(voice_response)
                except Exception as e:
                    logger.exception(f"Error synthesizing response: {e}")
        else:
            await message.reply(
                f"Выполняю команду: {result['action']} "
                f"(уверенность: {result['confidence']:.2f})"
            )
    else:
        # Сообщение о нераспознанной команде
        help_hint = (
            "Используйте /help для просмотра доступных команд."
        )
        
        # Если хотя бы минимальная уверенность, предлагаем возможную команду
        if result["confidence"] > 0.3:
            await message.reply(
                f"🤔 Не удалось распознать команду. Возможно, вы имели в виду "
                f"'{result['action']}'?\n\n{help_hint}"
            )
        else:
            await message.reply(
                f"❓ Не удалось распознать команду. {help_hint}"
            )
