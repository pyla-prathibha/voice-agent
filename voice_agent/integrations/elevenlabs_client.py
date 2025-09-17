"""
ElevenLabs integration for Speech-to-Text and Text-to-Speech.
"""

from typing import AsyncGenerator, Optional

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    aiohttp = None

import structlog

try:
    from elevenlabs import Voice, VoiceSettings, generate, stream
    from elevenlabs.client import ElevenLabs
    ELEVENLABS_AVAILABLE = True
except ImportError:
    # Fallback for testing/development
    ELEVENLABS_AVAILABLE = False
    Voice = None
    VoiceSettings = None
    generate = None
    stream = None
    ElevenLabs = None
from ..core.config import ElevenLabsConfig
from ..utils.audio_processing import resample_audio, normalize_audio_volume

logger = structlog.get_logger(__name__)


class ElevenLabsSTTClient:
    """ElevenLabs Speech-to-Text client."""
    
    def __init__(self, config: ElevenLabsConfig):
        """
        Initialize STT client.
        
        Args:
            config: ElevenLabs configuration
        """
        self.config = config
        if ELEVENLABS_AVAILABLE:
            self.client = ElevenLabs(api_key=config.api_key)
        else:
            self.client = None
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> Optional[object]:
        """Get or create aiohttp session."""
        if not AIOHTTP_AVAILABLE:
            return None
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def transcribe_audio(self, audio_data: bytes, language: str = "en") -> str:
        """
        Transcribe audio data to text.
        
        Args:
            audio_data: Raw audio data
            language: Language code for transcription
            
        Returns:
            Transcribed text
        """
        try:
            session = await self._get_session()
            
            # Prepare form data for API request
            data = aiohttp.FormData()
            data.add_field('audio', io.BytesIO(audio_data), filename='audio.wav', content_type='audio/wav')
            data.add_field('model', 'whisper-1')
            
            headers = {
                'Authorization': f'Bearer {self.config.api_key}'
            }
            
            # Make API request to ElevenLabs STT endpoint
            async with session.post(
                'https://api.elevenlabs.io/v1/speech-to-text',
                data=data,
                headers=headers
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    transcript = result.get('text', '').strip()
                    
                    logger.info("Audio transcribed", transcript=transcript, audio_size=len(audio_data))
                    return transcript
                else:
                    error_text = await response.text()
                    logger.error("STT API error", status=response.status, error=error_text)
                    return ""
        
        except Exception as e:
            logger.error("Error transcribing audio", error=str(e))
            return ""
    
    async def transcribe_stream(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        language: str = "en"
    ) -> AsyncGenerator[str, None]:
        """
        Transcribe streaming audio data.
        
        Args:
            audio_stream: Async generator of audio chunks
            language: Language code for transcription
            
        Yields:
            Transcribed text chunks
        """
        audio_buffer = bytearray()
        min_chunk_size = 16000 * 2  # 1 second of 16kHz 16-bit audio
        
        async for audio_chunk in audio_stream:
            audio_buffer.extend(audio_chunk)
            
            # Process when we have enough audio data
            if len(audio_buffer) >= min_chunk_size:
                transcript = await self.transcribe_audio(bytes(audio_buffer), language)
                if transcript:
                    yield transcript
                
                # Keep some overlap for better continuity
                overlap_size = min_chunk_size // 4
                audio_buffer = audio_buffer[-overlap_size:]
        
        # Process remaining audio
        if audio_buffer:
            transcript = await self.transcribe_audio(bytes(audio_buffer), language)
            if transcript:
                yield transcript
    
    async def close(self):
        """Close the client and cleanup resources."""
        if self.session and not self.session.closed:
            await self.session.close()


class ElevenLabsTTSClient:
    """ElevenLabs Text-to-Speech client."""
    
    def __init__(self, config: ElevenLabsConfig):
        """
        Initialize TTS client.
        
        Args:
            config: ElevenLabs configuration
        """
        self.config = config
        if ELEVENLABS_AVAILABLE:
            self.client = ElevenLabs(api_key=config.api_key)
            
            # Default voice settings
            self.voice_settings = VoiceSettings(
                stability=0.75,
                similarity_boost=0.75,
                style=0.0,
                use_speaker_boost=True
            )
        else:
            self.client = None
            self.voice_settings = None
    
    async def synthesize_text(
        self,
        text: str,
        voice_id: Optional[str] = None,
        model: str = "eleven_multilingual_v2"
    ) -> bytes:
        """
        Synthesize text to speech.
        
        Args:
            text: Text to synthesize
            voice_id: Voice ID to use (defaults to config voice_id)
            model: TTS model to use
            
        Returns:
            Audio data as bytes
        """
        if not text.strip():
            return b""
        
        try:
            voice_id = voice_id or self.config.voice_id
            
            # Use sync generate and run in thread pool
            def _generate():
                return generate(
                    text=text,
                    voice=Voice(
                        voice_id=voice_id,
                        settings=self.voice_settings
                    ),
                    model=model,
                    api_key=self.config.api_key
                )
            
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            audio_data = await loop.run_in_executor(None, _generate)
            
            # Convert generator to bytes if needed
            if hasattr(audio_data, '__iter__') and not isinstance(audio_data, (bytes, bytearray)):
                audio_bytes = b''.join(audio_data)
            else:
                audio_bytes = audio_data
            
            logger.info("Text synthesized", text=text[:100], audio_size=len(audio_bytes))
            return audio_bytes
            
        except Exception as e:
            logger.error("Error synthesizing text", error=str(e), text=text[:100])
            return b""
    
    async def synthesize_stream(
        self,
        text: str,
        voice_id: Optional[str] = None,
        model: str = "eleven_multilingual_v2"
    ) -> AsyncGenerator[bytes, None]:
        """
        Synthesize text to speech with streaming output.
        
        Args:
            text: Text to synthesize
            voice_id: Voice ID to use
            model: TTS model to use
            
        Yields:
            Audio data chunks
        """
        if not text.strip():
            return
        
        try:
            voice_id = voice_id or self.config.voice_id
            
            def _stream():
                return stream(
                    text=text,
                    voice=Voice(
                        voice_id=voice_id,
                        settings=self.voice_settings
                    ),
                    model=model,
                    api_key=self.config.api_key
                )
            
            # Run in thread pool
            loop = asyncio.get_event_loop()
            audio_stream = await loop.run_in_executor(None, _stream)
            
            # Yield chunks
            for chunk in audio_stream:
                yield chunk
                # Allow other coroutines to run
                await asyncio.sleep(0)
            
        except Exception as e:
            logger.error("Error streaming synthesis", error=str(e), text=text[:100])
    
    async def get_available_voices(self) -> list:
        """
        Get list of available voices.
        
        Returns:
            List of voice information
        """
        try:
            def _get_voices():
                return self.client.voices.get_all()
            
            loop = asyncio.get_event_loop()
            voices = await loop.run_in_executor(None, _get_voices)
            
            return [
                {
                    'voice_id': voice.voice_id,
                    'name': voice.name,
                    'category': voice.category,
                    'description': voice.description
                }
                for voice in voices.voices
            ]
            
        except Exception as e:
            logger.error("Error getting voices", error=str(e))
            return []
    
    def set_voice_settings(
        self,
        stability: float = 0.75,
        similarity_boost: float = 0.75,
        style: float = 0.0,
        use_speaker_boost: bool = True
    ):
        """
        Update voice settings.
        
        Args:
            stability: Voice stability (0.0-1.0)
            similarity_boost: Similarity boost (0.0-1.0)
            style: Style setting (0.0-1.0)
            use_speaker_boost: Whether to use speaker boost
        """
        self.voice_settings = VoiceSettings(
            stability=stability,
            similarity_boost=similarity_boost,
            style=style,
            use_speaker_boost=use_speaker_boost
        )


class ElevenLabsClient:
    """Combined ElevenLabs client for both STT and TTS."""
    
    def __init__(self, config: ElevenLabsConfig):
        """
        Initialize combined client.
        
        Args:
            config: ElevenLabs configuration
        """
        self.config = config
        self.stt = ElevenLabsSTTClient(config)
        self.tts = ElevenLabsTTSClient(config)
    
    async def speech_to_text(self, audio_data: bytes, language: str = "en") -> str:
        """
        Convert speech to text.
        
        Args:
            audio_data: Raw audio data
            language: Language code
            
        Returns:
            Transcribed text
        """
        return await self.stt.transcribe_audio(audio_data, language)
    
    async def text_to_speech(
        self,
        text: str,
        voice_id: Optional[str] = None,
        streaming: bool = False
    ) -> bytes | AsyncGenerator[bytes, None]:
        """
        Convert text to speech.
        
        Args:
            text: Text to synthesize
            voice_id: Voice ID to use
            streaming: Whether to return streaming response
            
        Returns:
            Audio data or async generator of audio chunks
        """
        if streaming:
            return self.tts.synthesize_stream(text, voice_id)
        else:
            return await self.tts.synthesize_text(text, voice_id)
    
    async def process_conversation_turn(
        self,
        audio_data: bytes,
        response_text: str,
        input_language: str = "en",
        voice_id: Optional[str] = None
    ) -> tuple[str, bytes]:
        """
        Process a complete conversation turn: STT + TTS.
        
        Args:
            audio_data: Input audio data
            response_text: Text response to synthesize
            input_language: Language for STT
            voice_id: Voice ID for TTS
            
        Returns:
            Tuple of (transcribed_text, response_audio)
        """
        # Transcribe input audio
        transcript = await self.speech_to_text(audio_data, input_language)
        
        # Synthesize response
        response_audio = await self.text_to_speech(response_text, voice_id)
        
        return transcript, response_audio
    
    async def get_voices(self) -> list:
        """Get available voices."""
        return await self.tts.get_available_voices()
    
    def configure_voice(
        self,
        stability: float = 0.75,
        similarity_boost: float = 0.75,
        style: float = 0.0,
        use_speaker_boost: bool = True
    ):
        """Configure TTS voice settings."""
        self.tts.set_voice_settings(stability, similarity_boost, style, use_speaker_boost)
    
    async def close(self):
        """Close client and cleanup resources."""
        await self.stt.close()