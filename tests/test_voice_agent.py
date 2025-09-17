"""
Tests for the Voice Agent system.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from voice_agent.core.config import VoiceAgentConfig, PlivoConfig, ElevenLabsConfig, OpenAIConfig
from voice_agent.core.voice_agent import VoiceAgent
from voice_agent.utils.audio_processing import VoiceActivityDetector, TurnTakingManager


class TestVoiceAgentConfig:
    """Tests for VoiceAgentConfig."""
    
    def test_config_validation_missing_fields(self):
        """Test configuration validation with missing fields."""
        config = VoiceAgentConfig(
            plivo=PlivoConfig(auth_id="", auth_token=""),
            elevenlabs=ElevenLabsConfig(api_key=""),
            openai=OpenAIConfig(api_key="")
        )
        
        with pytest.raises(ValueError, match="Missing required environment variables"):
            config.validate_required_fields()
    
    def test_config_validation_success(self):
        """Test successful configuration validation."""
        config = VoiceAgentConfig(
            plivo=PlivoConfig(auth_id="test_id", auth_token="test_token"),
            elevenlabs=ElevenLabsConfig(api_key="test_key"),
            openai=OpenAIConfig(api_key="test_key")
        )
        
        # Should not raise
        config.validate_required_fields()
    
    @patch.dict('os.environ', {
        'PLIVO_AUTH_ID': 'test_id',
        'PLIVO_AUTH_TOKEN': 'test_token',
        'ELEVENLABS_API_KEY': 'test_key',
        'OPENAI_API_KEY': 'test_key'
    })
    def test_config_from_env(self):
        """Test configuration loading from environment."""
        config = VoiceAgentConfig.from_env()
        
        assert config.plivo.auth_id == 'test_id'
        assert config.plivo.auth_token == 'test_token'
        assert config.elevenlabs.api_key == 'test_key'
        assert config.openai.api_key == 'test_key'


class TestVoiceActivityDetector:
    """Tests for VoiceActivityDetector."""
    
    def test_vad_initialization(self):
        """Test VAD initialization."""
        vad = VoiceActivityDetector(sample_rate=16000, aggressiveness=2)
        assert vad.sample_rate == 16000
        assert vad.frame_size == 480  # 30ms at 16kHz
    
    def test_is_speech_invalid_chunk(self):
        """Test VAD with invalid audio chunk."""
        vad = VoiceActivityDetector()
        
        # Too short chunk
        result = vad.is_speech(b'short')
        assert result is False
    
    def test_is_speech_valid_chunk(self):
        """Test VAD with valid audio chunk."""
        vad = VoiceActivityDetector()
        
        # Create properly sized chunk (480 samples * 2 bytes = 960 bytes)
        audio_chunk = b'\x00\x01' * 480
        
        # Should not raise exception
        result = vad.is_speech(audio_chunk)
        assert isinstance(result, bool)


class TestTurnTakingManager:
    """Tests for TurnTakingManager."""
    
    def test_initialization(self):
        """Test turn-taking manager initialization."""
        manager = TurnTakingManager(
            silence_duration_ms=1000,
            min_speech_duration_ms=300,
            sample_rate=16000
        )
        
        assert manager.silence_duration_ms == 1000
        assert manager.min_speech_duration_ms == 300
        assert not manager.is_speaking
    
    def test_reset_state(self):
        """Test state reset."""
        manager = TurnTakingManager()
        
        # Set some state
        manager.is_speaking = True
        manager.speech_start_time = 123.0
        manager.accumulated_audio.extend(b'test')
        
        # Reset
        manager._reset_state()
        
        assert not manager.is_speaking
        assert manager.speech_start_time is None
        assert len(manager.accumulated_audio) == 0
    
    def test_force_end_turn(self):
        """Test forcing turn end."""
        manager = TurnTakingManager()
        
        # Add some audio
        test_audio = b'test_audio'
        manager.accumulated_audio.extend(test_audio)
        
        # Force end turn
        result = manager.force_end_turn()
        
        assert result == test_audio
        assert len(manager.accumulated_audio) == 0


class TestVoiceAgent:
    """Tests for VoiceAgent."""
    
    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        return VoiceAgentConfig(
            plivo=PlivoConfig(auth_id="test_id", auth_token="test_token"),
            elevenlabs=ElevenLabsConfig(api_key="test_key"),
            openai=OpenAIConfig(api_key="test_key")
        )
    
    @pytest.fixture
    def voice_agent(self, mock_config):
        """Create VoiceAgent instance with mocked dependencies."""
        with patch('voice_agent.core.voice_agent.PlivoVoiceClient'), \
             patch('voice_agent.core.voice_agent.ElevenLabsClient'), \
             patch('voice_agent.core.voice_agent.OpenAILLMClient'), \
             patch('voice_agent.core.voice_agent.PlivoWebServer'):
            
            agent = VoiceAgent(mock_config)
            return agent
    
    def test_voice_agent_initialization(self, voice_agent):
        """Test VoiceAgent initialization."""
        assert voice_agent.config is not None
        assert voice_agent.plivo_client is not None
        assert voice_agent.elevenlabs_client is not None
        assert voice_agent.openai_client is not None
        assert voice_agent.web_server is not None
        assert len(voice_agent.active_sessions) == 0
    
    def test_set_callbacks(self, voice_agent):
        """Test setting callbacks."""
        mock_callback = Mock()
        
        voice_agent.set_callbacks(
            on_call_started=mock_callback,
            on_call_ended=mock_callback,
            on_transcript_received=mock_callback,
            on_response_generated=mock_callback
        )
        
        assert voice_agent.on_call_started == mock_callback
        assert voice_agent.on_call_ended == mock_callback
        assert voice_agent.on_transcript_received == mock_callback
        assert voice_agent.on_response_generated == mock_callback
    
    @pytest.mark.asyncio
    async def test_make_call(self, voice_agent):
        """Test making an outbound call."""
        # Mock the plivo client
        voice_agent.plivo_client.make_call = AsyncMock(return_value="test_uuid")
        
        call_uuid = await voice_agent.make_call(
            to_number="+1234567890",
            from_number="+0987654321",
            system_prompt="Test prompt"
        )
        
        assert call_uuid == "test_uuid"
        assert "test_uuid" in voice_agent.active_sessions
        assert voice_agent.active_sessions["test_uuid"]["system_prompt"] == "Test prompt"
        
        # Verify plivo client was called correctly
        voice_agent.plivo_client.make_call.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_hangup_call(self, voice_agent):
        """Test hanging up a call."""
        # Setup active session
        voice_agent.active_sessions["test_uuid"] = {"status": "active"}
        
        # Mock the plivo client
        voice_agent.plivo_client.hangup_call = AsyncMock(return_value=True)
        
        result = await voice_agent.hangup_call("test_uuid")
        
        assert result is True
        assert "test_uuid" not in voice_agent.active_sessions
        
        voice_agent.plivo_client.hangup_call.assert_called_once_with("test_uuid")
    
    @pytest.mark.asyncio
    async def test_update_system_prompt(self, voice_agent):
        """Test updating system prompt."""
        # Setup active session
        voice_agent.active_sessions["test_uuid"] = {
            "conversation_id": "test_conv"
        }
        
        # Mock conversation
        mock_conversation = Mock()
        voice_agent.openai_client.conversations = {"test_conv": mock_conversation}
        
        await voice_agent.update_system_prompt("test_uuid", "New prompt")
        
        assert voice_agent.active_sessions["test_uuid"]["system_prompt"] == "New prompt"
        mock_conversation.set_system_prompt.assert_called_once_with("New prompt")
    
    @pytest.mark.asyncio
    async def test_send_message_to_call(self, voice_agent):
        """Test sending message to call."""
        # Setup active session
        voice_agent.active_sessions["test_uuid"] = {"status": "active"}
        
        # Mock clients
        voice_agent.elevenlabs_client.text_to_speech = AsyncMock(return_value=b"audio_data")
        voice_agent.plivo_client.send_audio_to_call = AsyncMock()
        
        await voice_agent.send_message_to_call("test_uuid", "Test message")
        
        voice_agent.elevenlabs_client.text_to_speech.assert_called_once_with("Test message")
        voice_agent.plivo_client.send_audio_to_call.assert_called_once_with("test_uuid", b"audio_data")
    
    @pytest.mark.asyncio
    async def test_send_message_to_inactive_call(self, voice_agent):
        """Test sending message to inactive call raises error."""
        with pytest.raises(ValueError, match="No active session"):
            await voice_agent.send_message_to_call("invalid_uuid", "Test message")
    
    def test_get_stats(self, voice_agent):
        """Test getting statistics."""
        # Setup some data
        voice_agent.active_sessions["test_uuid"] = {"status": "active"}
        voice_agent.plivo_client.get_active_calls = Mock(return_value={"test_uuid": {}})
        voice_agent.openai_client.get_conversation_stats = Mock(return_value={"total": 1})
        
        stats = voice_agent.get_stats()
        
        assert stats['active_sessions'] == 1
        assert stats['active_calls'] == 1
        assert 'conversations' in stats
        assert 'config' in stats
    
    def test_get_active_calls(self, voice_agent):
        """Test getting active calls."""
        # Setup data
        voice_agent.active_sessions["test_uuid"] = {"status": "active"}
        voice_agent.plivo_client.get_active_calls = Mock(return_value={"test_uuid": {"plivo": "data"}})
        
        active_calls = voice_agent.get_active_calls()
        
        assert "test_uuid" in active_calls
        assert active_calls["test_uuid"]["status"] == "active"
        assert active_calls["test_uuid"]["plivo_info"]["plivo"] == "data"
    
    def test_get_conversation_history(self, voice_agent):
        """Test getting conversation history."""
        # Setup session
        voice_agent.active_sessions["test_uuid"] = {"conversation_id": "test_conv"}
        voice_agent.openai_client.get_conversation_history = Mock(return_value=[{"role": "user", "content": "Hello"}])
        
        history = voice_agent.get_conversation_history("test_uuid")
        
        assert len(history) == 1
        assert history[0]["content"] == "Hello"
        
        voice_agent.openai_client.get_conversation_history.assert_called_once_with("test_conv")
    
    def test_get_conversation_history_invalid_call(self, voice_agent):
        """Test getting conversation history for invalid call."""
        history = voice_agent.get_conversation_history("invalid_uuid")
        assert history == []


@pytest.mark.asyncio
async def test_safe_callback():
    """Test safe callback execution."""
    from voice_agent.core.voice_agent import VoiceAgent
    
    with patch('voice_agent.core.voice_agent.PlivoVoiceClient'), \
         patch('voice_agent.core.voice_agent.ElevenLabsClient'), \
         patch('voice_agent.core.voice_agent.OpenAILLMClient'), \
         patch('voice_agent.core.voice_agent.PlivoWebServer'):
        
        config = VoiceAgentConfig(
            plivo=PlivoConfig(auth_id="test", auth_token="test"),
            elevenlabs=ElevenLabsConfig(api_key="test"),
            openai=OpenAIConfig(api_key="test")
        )
        
        agent = VoiceAgent(config)
        
        # Test successful async callback
        async_callback = AsyncMock()
        await agent._safe_callback(async_callback, "arg1", "arg2")
        async_callback.assert_called_once_with("arg1", "arg2")
        
        # Test successful sync callback
        sync_callback = Mock()
        await agent._safe_callback(sync_callback, "arg1", "arg2")
        sync_callback.assert_called_once_with("arg1", "arg2")
        
        # Test callback that raises exception (should not propagate)
        failing_callback = Mock(side_effect=Exception("Test error"))
        await agent._safe_callback(failing_callback, "arg1", "arg2")
        failing_callback.assert_called_once_with("arg1", "arg2")


if __name__ == "__main__":
    pytest.main([__file__])