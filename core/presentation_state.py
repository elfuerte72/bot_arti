from enum import Enum
from typing import Dict, Any, Optional

class PresentationState(Enum):
    NO_KEYNOTE = "no_keynote"        # Keynote не запущен
    NO_PRESENTATION = "no_presentation"  # Нет открытой презентации
    READY = "ready"                  # Презентация готова, но не запущена
    PLAYING = "playing"              # Презентация воспроизводится
    PAUSED = "paused"                # Презентация на паузе

class PresentationContext:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PresentationContext, cls).__new__(cls)
            cls._instance.state = PresentationState.NO_KEYNOTE
            cls._instance.current_slide = 0
            cls._instance.total_slides = 0
            cls._instance.presentation_name = None
        return cls._instance
    
    async def update_state(self) -> None:
        """Обновляет текущее состояние презентации."""
        from slides import keynote_controller
        
        # Проверяем, запущен ли Keynote
        if not await keynote_controller.is_keynote_running():
            self.state = PresentationState.NO_KEYNOTE
            return
            
        # Проверяем, есть ли презентация
        if not await keynote_controller.is_presentation_active():
            self.state = PresentationState.NO_PRESENTATION
            return
            
        # Проверяем статус воспроизведения
        status = await keynote_controller.get_presentation_status()
        if status["success"]:
            if "data" in status:
                self.current_slide = status["data"].get("current_slide", 0)
                self.total_slides = status["data"].get("total_slides", 0)
                self.presentation_name = status["data"].get("document_name", "")
                
                if status["data"].get("is_playing", False):
                    self.state = PresentationState.PLAYING
                else:
                    self.state = PresentationState.PAUSED
            else:
                self.state = PresentationState.READY
    
    def get_status_message(self) -> str:
        """Возвращает понятное сообщение о текущем состоянии."""
        if self.state == PresentationState.NO_KEYNOTE:
            return "Keynote не запущен. Я запущу его для вас."
        elif self.state == PresentationState.NO_PRESENTATION:
            return "Нет открытой презентации. Откройте презентацию в Keynote."
        elif self.state == PresentationState.READY:
            return f"Презентация '{self.presentation_name}' готова к запуску."
        elif self.state == PresentationState.PLAYING:
            return f"Презентация воспроизводится, слайд {self.current_slide} из {self.total_slides}."
        elif self.state == PresentationState.PAUSED:
            return f"Презентация на паузе, слайд {self.current_slide} из {self.total_slides}."
        
    async def validate_action(self, action: str) -> Dict[str, Any]:
        """Проверяет, можно ли выполнить действие в текущем состоянии."""
        await self.update_state()
        
        valid_actions = {
            PresentationState.NO_KEYNOTE: ["start"],
            PresentationState.NO_PRESENTATION: ["status"],
            PresentationState.READY: ["start", "status", "next_slide", "previous_slide", "goto_slide"],
            PresentationState.PLAYING: ["next_slide", "previous_slide", "pause", "end_presentation", "status", "goto_slide", "speak_next_block", "repeat_last_block"],
            PresentationState.PAUSED: ["resume", "next_slide", "previous_slide", "end_presentation", "status", "goto_slide"]
        }
        
        if action in valid_actions.get(self.state, []):
            return {
                "valid": True,
                "message": None
            }
        
        # Контекстные подсказки в зависимости от состояния
        messages = {
            PresentationState.NO_KEYNOTE: "Сначала нужно запустить Keynote. Скажите 'запустить презентацию'.",
            PresentationState.NO_PRESENTATION: "Откройте презентацию в Keynote перед использованием команд.",
            PresentationState.READY: f"Презентация не запущена. Скажите 'начать' чтобы запустить '{self.presentation_name}'.",
            PresentationState.PLAYING: "Эта команда недоступна при воспроизведении презентации.",
            PresentationState.PAUSED: "Презентация на паузе. Скажите 'продолжить' для возобновления."
        }
        
        return {
            "valid": False,
            "message": messages.get(self.state, "Эта команда недоступна сейчас.")
        } 