"""
Voice Agent - Real-time voice interaction system using Plivo + ElevenLabs + GPT.
"""

__version__ = "1.0.0"
__author__ = "Voice Agent Team"

from .core.voice_agent import VoiceAgent
from .core.config import VoiceAgentConfig

__all__ = ["VoiceAgent", "VoiceAgentConfig"]