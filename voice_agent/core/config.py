"""
Configuration management for the Voice Agent system.
"""

import os
from typing import Optional

try:
    from pydantic import BaseModel, Field
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    # Fallback implementation
    class BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
    
    def Field(**kwargs):
        return kwargs.get('default')

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class PlivoConfig(BaseModel):
    """Plivo telephony configuration."""
    auth_id: str = Field(..., description="Plivo Auth ID")
    auth_token: str = Field(..., description="Plivo Auth Token")


class ElevenLabsConfig(BaseModel):
    """ElevenLabs STT/TTS configuration."""
    api_key: str = Field(..., description="ElevenLabs API key")
    voice_id: str = Field(default="21m00Tcm4TlvDq8ikWAM", description="Voice ID for TTS")


class OpenAIConfig(BaseModel):
    """OpenAI LLM configuration."""
    api_key: str = Field(..., description="OpenAI API key")
    model: str = Field(default="gpt-4", description="LLM model to use")
    max_tokens: int = Field(default=500, description="Maximum tokens for response")
    temperature: float = Field(default=0.7, description="Response temperature")


class AudioConfig(BaseModel):
    """Audio processing configuration."""
    sample_rate: int = Field(default=16000, description="Audio sample rate")
    chunk_size: int = Field(default=1024, description="Audio chunk size")
    voice_activity_threshold: float = Field(default=0.5, description="VAD threshold")
    silence_duration_ms: int = Field(default=1000, description="Silence duration for turn-taking")


class ServerConfig(BaseModel):
    """Server configuration."""
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8080, description="Server port")


class VoiceAgentConfig(BaseModel):
    """Main configuration for the Voice Agent system."""
    plivo: PlivoConfig
    elevenlabs: ElevenLabsConfig
    openai: OpenAIConfig
    audio: AudioConfig = Field(default_factory=AudioConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)

    @classmethod
    def from_env(cls) -> "VoiceAgentConfig":
        """Create configuration from environment variables."""
        return cls(
            plivo=PlivoConfig(
                auth_id=os.getenv("PLIVO_AUTH_ID", ""),
                auth_token=os.getenv("PLIVO_AUTH_TOKEN", "")
            ),
            elevenlabs=ElevenLabsConfig(
                api_key=os.getenv("ELEVENLABS_API_KEY", ""),
                voice_id=os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
            ),
            openai=OpenAIConfig(
                api_key=os.getenv("OPENAI_API_KEY", ""),
                model=os.getenv("LLM_MODEL", "gpt-4"),
                max_tokens=int(os.getenv("LLM_MAX_TOKENS", "500")),
                temperature=float(os.getenv("LLM_TEMPERATURE", "0.7"))
            ),
            audio=AudioConfig(
                sample_rate=int(os.getenv("SAMPLE_RATE", "16000")),
                chunk_size=int(os.getenv("CHUNK_SIZE", "1024")),
                voice_activity_threshold=float(os.getenv("VOICE_ACTIVITY_THRESHOLD", "0.5")),
                silence_duration_ms=int(os.getenv("SILENCE_DURATION_MS", "1000"))
            ),
            server=ServerConfig(
                host=os.getenv("VOICE_AGENT_HOST", "0.0.0.0"),
                port=int(os.getenv("VOICE_AGENT_PORT", "8080"))
            )
        )

    def validate_required_fields(self) -> None:
        """Validate that all required API keys are present."""
        missing_fields = []
        
        if not self.plivo.auth_id:
            missing_fields.append("PLIVO_AUTH_ID")
        if not self.plivo.auth_token:
            missing_fields.append("PLIVO_AUTH_TOKEN")
        if not self.elevenlabs.api_key:
            missing_fields.append("ELEVENLABS_API_KEY")
        if not self.openai.api_key:
            missing_fields.append("OPENAI_API_KEY")
        
        if missing_fields:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_fields)}")