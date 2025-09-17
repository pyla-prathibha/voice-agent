"""
Audio processing utilities including voice activity detection and turn-taking.
"""

import asyncio
import time
from typing import AsyncGenerator, Optional, Callable

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    np = None

try:
    import webrtcvad
    WEBRTCVAD_AVAILABLE = True
except ImportError:
    WEBRTCVAD_AVAILABLE = False
    webrtcvad = None

import structlog

logger = structlog.get_logger(__name__)


class VoiceActivityDetector:
    """Voice Activity Detection using WebRTC VAD."""
    
    def __init__(self, sample_rate: int = 16000, aggressiveness: int = 2):
        """
        Initialize VAD.
        
        Args:
            sample_rate: Audio sample rate (8000, 16000, 32000, or 48000)
            aggressiveness: VAD aggressiveness (0-3, higher = more aggressive)
        """
        self.sample_rate = sample_rate
        if WEBRTCVAD_AVAILABLE:
            self.vad = webrtcvad.Vad(aggressiveness)
        else:
            self.vad = None
        self.frame_duration_ms = 30  # Frame duration in milliseconds
        self.frame_size = int(sample_rate * self.frame_duration_ms / 1000)
        
    def is_speech(self, audio_chunk: bytes) -> bool:
        """
        Detect if audio chunk contains speech.
        
        Args:
            audio_chunk: Raw audio data
            
        Returns:
            True if speech is detected, False otherwise
        """
        try:
            # Ensure chunk is the right size for VAD
            if len(audio_chunk) != self.frame_size * 2:  # 2 bytes per sample for 16-bit
                return False
            
            if not WEBRTCVAD_AVAILABLE or self.vad is None:
                # Fallback: simple energy-based detection
                if len(audio_chunk) < 2:
                    return False
                # Convert to numpy array and check energy
                try:
                    if not NUMPY_AVAILABLE:
                        # Simple byte-based energy estimation  
                        energy = sum(abs(b - 128) for b in audio_chunk) / len(audio_chunk)
                        return energy > 10
                    else:
                        audio_array = np.frombuffer(audio_chunk, dtype=np.int16)
                        energy = np.mean(np.abs(audio_array))
                        return energy > 100  # Simple threshold
                except:
                    return False
            
            return self.vad.is_speech(audio_chunk, self.sample_rate)
        except Exception as e:
            logger.warning("VAD error", error=str(e))
            return False


class TurnTakingManager:
    """Manages turn-taking in conversations based on voice activity and silence."""
    
    def __init__(
        self,
        silence_duration_ms: int = 1000,
        min_speech_duration_ms: int = 300,
        sample_rate: int = 16000
    ):
        """
        Initialize turn-taking manager.
        
        Args:
            silence_duration_ms: Duration of silence before considering turn ended
            min_speech_duration_ms: Minimum speech duration to consider a valid turn
            sample_rate: Audio sample rate
        """
        self.silence_duration_ms = silence_duration_ms
        self.min_speech_duration_ms = min_speech_duration_ms
        self.sample_rate = sample_rate
        
        self.vad = VoiceActivityDetector(sample_rate)
        
        # State tracking
        self.is_speaking = False
        self.speech_start_time: Optional[float] = None
        self.last_speech_time: Optional[float] = None
        self.accumulated_audio = bytearray()
        
    def process_audio_chunk(self, audio_chunk: bytes) -> tuple[bool, Optional[bytes]]:
        """
        Process audio chunk and determine if turn is complete.
        
        Args:
            audio_chunk: Raw audio data
            
        Returns:
            Tuple of (turn_complete, audio_data_if_complete)
        """
        current_time = time.time()
        has_speech = self.vad.is_speech(audio_chunk)
        
        # Accumulate audio data
        self.accumulated_audio.extend(audio_chunk)
        
        if has_speech:
            if not self.is_speaking:
                # Start of speech
                self.is_speaking = True
                self.speech_start_time = current_time
                logger.debug("Speech started")
            
            self.last_speech_time = current_time
            
        else:
            # No speech detected
            if self.is_speaking and self.last_speech_time:
                silence_duration = (current_time - self.last_speech_time) * 1000
                
                if silence_duration >= self.silence_duration_ms:
                    # End of turn detected
                    speech_duration = (self.last_speech_time - self.speech_start_time) * 1000 if self.speech_start_time else 0
                    
                    if speech_duration >= self.min_speech_duration_ms:
                        # Valid turn completed
                        audio_data = bytes(self.accumulated_audio)
                        self._reset_state()
                        logger.debug("Turn completed", speech_duration_ms=speech_duration)
                        return True, audio_data
                    else:
                        # Too short, ignore
                        self._reset_state()
                        logger.debug("Speech too short, ignoring", speech_duration_ms=speech_duration)
        
        return False, None
    
    def _reset_state(self):
        """Reset internal state."""
        self.is_speaking = False
        self.speech_start_time = None
        self.last_speech_time = None
        self.accumulated_audio.clear()
    
    def force_end_turn(self) -> Optional[bytes]:
        """Force end current turn and return accumulated audio."""
        if self.accumulated_audio:
            audio_data = bytes(self.accumulated_audio)
            self._reset_state()
            return audio_data
        return None


class AudioStreamProcessor:
    """Processes audio streams with voice activity detection and turn-taking."""
    
    def __init__(
        self,
        sample_rate: int = 16000,
        chunk_size: int = 1024,
        silence_duration_ms: int = 1000,
        on_turn_complete: Optional[Callable[[bytes], None]] = None
    ):
        """
        Initialize audio stream processor.
        
        Args:
            sample_rate: Audio sample rate
            chunk_size: Size of audio chunks to process
            silence_duration_ms: Silence duration for turn detection
            on_turn_complete: Callback when a turn is completed
        """
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.turn_manager = TurnTakingManager(silence_duration_ms, sample_rate=sample_rate)
        self.on_turn_complete = on_turn_complete
        
    async def process_stream(self, audio_stream: AsyncGenerator[bytes, None]):
        """
        Process an async audio stream.
        
        Args:
            audio_stream: Async generator yielding audio chunks
        """
        async for audio_chunk in audio_stream:
            await self.process_chunk(audio_chunk)
    
    async def process_chunk(self, audio_chunk: bytes):
        """
        Process a single audio chunk.
        
        Args:
            audio_chunk: Raw audio data
        """
        turn_complete, audio_data = self.turn_manager.process_audio_chunk(audio_chunk)
        
        if turn_complete and audio_data and self.on_turn_complete:
            # Run callback in a separate task to avoid blocking
            asyncio.create_task(self._handle_turn_complete(audio_data))
    
    async def _handle_turn_complete(self, audio_data: bytes):
        """Handle turn completion."""
        try:
            if self.on_turn_complete:
                if asyncio.iscoroutinefunction(self.on_turn_complete):
                    await self.on_turn_complete(audio_data)
                else:
                    self.on_turn_complete(audio_data)
        except Exception as e:
            logger.error("Error in turn complete callback", error=str(e))


def resample_audio(audio_data: bytes, from_rate: int, to_rate: int) -> bytes:
    """
    Resample audio data to different sample rate.
    
    Args:
        audio_data: Raw audio data
        from_rate: Source sample rate
        to_rate: Target sample rate
        
    Returns:
        Resampled audio data
    """
    if from_rate == to_rate:
        return audio_data
    
    if not NUMPY_AVAILABLE:
        # Simple resampling fallback - just return original data
        logger.warning("NumPy not available, skipping audio resampling")
        return audio_data
    
    # Convert bytes to numpy array
    audio_array = np.frombuffer(audio_data, dtype=np.int16)
    
    # Simple linear interpolation resampling
    ratio = to_rate / from_rate
    new_length = int(len(audio_array) * ratio)
    
    # Create new time indices
    old_indices = np.arange(len(audio_array))
    new_indices = np.linspace(0, len(audio_array) - 1, new_length)
    
    # Interpolate
    resampled = np.interp(new_indices, old_indices, audio_array)
    
    return resampled.astype(np.int16).tobytes()


def normalize_audio_volume(audio_data: bytes, target_db: float = -20.0) -> bytes:
    """
    Normalize audio volume to target dB level.
    
    Args:
        audio_data: Raw audio data
        target_db: Target dB level
        
    Returns:
        Volume-normalized audio data
    """
    if not NUMPY_AVAILABLE:
        # Simple normalization fallback
        logger.warning("NumPy not available, skipping audio normalization")
        return audio_data
        
    audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
    
    # Calculate RMS and current dB level
    rms = np.sqrt(np.mean(audio_array ** 2))
    if rms == 0:
        return audio_data
    
    current_db = 20 * np.log10(rms / 32767.0)  # 32767 is max value for int16
    
    # Calculate gain needed
    gain_db = target_db - current_db
    gain_linear = 10 ** (gain_db / 20)
    
    # Apply gain and clip
    normalized = audio_array * gain_linear
    normalized = np.clip(normalized, -32767, 32767)
    
    return normalized.astype(np.int16).tobytes()