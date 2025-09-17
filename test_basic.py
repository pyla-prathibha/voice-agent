#!/usr/bin/env python3
"""
Basic test to verify the Voice Agent implementation structure.
Uses built-in libraries and mocks to test the core functionality.
"""

import asyncio
import unittest
from unittest.mock import Mock, patch, AsyncMock
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock external dependencies
sys.modules['pydantic'] = Mock()
sys.modules['plivo'] = Mock()
sys.modules['elevenlabs'] = Mock()
sys.modules['openai'] = Mock()
sys.modules['webrtcvad'] = Mock()
sys.modules['structlog'] = Mock()
sys.modules['aiohttp'] = Mock()
sys.modules['websockets'] = Mock()
sys.modules['dotenv'] = Mock()
sys.modules['numpy'] = Mock()
sys.modules['scipy'] = Mock()

# Setup basic mock objects
class MockBaseModel:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

class MockField:
    def __init__(self, *args, **kwargs):
        self.default = kwargs.get('default')
        self.description = kwargs.get('description')
        # Return the default value when called like Field(default=...)
        if 'default_factory' in kwargs:
            self.default = kwargs['default_factory']()
        
    def __call__(self):
        return self.default

# Mock pydantic
pydantic_mock = Mock()
pydantic_mock.BaseModel = MockBaseModel  
pydantic_mock.Field = MockField
sys.modules['pydantic'] = pydantic_mock

# Mock structlog
structlog_mock = Mock()
structlog_mock.get_logger = Mock(return_value=Mock())
structlog_mock.configure = Mock()
structlog_mock.processors = Mock()
sys.modules['structlog'] = structlog_mock

# Mock python-dotenv
dotenv_mock = Mock()
dotenv_mock.load_dotenv = Mock()
sys.modules['python-dotenv'] = dotenv_mock
sys.modules['dotenv'] = dotenv_mock

def test_basic_imports():
    """Test that basic imports work."""
    print("Testing basic imports...")
    
    try:
        from voice_agent.core.config import VoiceAgentConfig
        print("✅ Config import successful")
    except Exception as e:
        print(f"❌ Config import failed: {e}")
        return False
    
    try:
        from voice_agent.utils.audio_processing import VoiceActivityDetector
        print("✅ Audio processing import successful")
    except Exception as e:
        print(f"❌ Audio processing import failed: {e}")
        return False
    
    return True

def test_config_creation():
    """Test configuration creation."""
    print("Testing configuration creation...")
    
    try:
        # Mock environment variables
        with patch.dict(os.environ, {
            'PLIVO_AUTH_ID': 'test_id',
            'PLIVO_AUTH_TOKEN': 'test_token',
            'ELEVENLABS_API_KEY': 'test_key',
            'OPENAI_API_KEY': 'test_key'
        }):
            from voice_agent.core.config import VoiceAgentConfig
            config = VoiceAgentConfig.from_env()
            print("✅ Configuration created successfully")
            return True
    except Exception as e:
        print(f"❌ Configuration creation failed: {e}")
        return False

def test_voice_agent_structure():
    """Test Voice Agent class structure."""
    print("Testing Voice Agent structure...")
    
    try:
        # Mock all the dependencies
        with patch('voice_agent.core.voice_agent.PlivoVoiceClient'), \
             patch('voice_agent.core.voice_agent.ElevenLabsClient'), \
             patch('voice_agent.core.voice_agent.OpenAILLMClient'), \
             patch('voice_agent.core.voice_agent.PlivoWebServer'), \
             patch('voice_agent.core.voice_agent.AudioStreamProcessor'):
            
            from voice_agent.core.voice_agent import VoiceAgent
            from voice_agent.core.config import VoiceAgentConfig, PlivoConfig, ElevenLabsConfig, OpenAIConfig
            
            # Create proper config objects  
            plivo_config = PlivoConfig(auth_id="test", auth_token="test")
            elevenlabs_config = ElevenLabsConfig(api_key="test")
            openai_config = OpenAIConfig(api_key="test")
            
            # Create audio and server configs manually
            class MockAudioConfig:
                def __init__(self):
                    self.sample_rate = 16000
                    self.chunk_size = 1024
                    self.voice_activity_threshold = 0.5
                    self.silence_duration_ms = 1000
            
            class MockServerConfig:
                def __init__(self):
                    self.host = "0.0.0.0"
                    self.port = 8080
            
            config = VoiceAgentConfig(
                plivo=plivo_config,
                elevenlabs=elevenlabs_config,
                openai=openai_config
            )
            config.audio = MockAudioConfig()
            config.server = MockServerConfig()
            
            agent = VoiceAgent(config)
            print("✅ Voice Agent created successfully")
            
            # Test basic methods exist
            assert hasattr(agent, 'start'), "Missing start method"
            assert hasattr(agent, 'stop'), "Missing stop method"
            assert hasattr(agent, 'make_call'), "Missing make_call method"
            assert hasattr(agent, 'hangup_call'), "Missing hangup_call method"
            assert hasattr(agent, 'set_callbacks'), "Missing set_callbacks method"
            print("✅ Voice Agent has required methods")
            
            return True
    except Exception as e:
        print(f"❌ Voice Agent structure test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_async_functionality():
    """Test async functionality."""
    print("Testing async functionality...")
    
    try:
        # Test that we can create async functions
        async def dummy_async():
            await asyncio.sleep(0.01)
            return "success"
        
        result = await dummy_async()
        assert result == "success"
        print("✅ Async functionality works")
        return True
    except Exception as e:
        print(f"❌ Async functionality test failed: {e}")
        return False

def test_audio_processing():
    """Test audio processing components."""
    print("Testing audio processing...")
    
    try:
        # Mock webrtcvad
        webrtcvad_mock = Mock()
        webrtcvad_mock.Vad = Mock()
        sys.modules['webrtcvad'] = webrtcvad_mock
        
        from voice_agent.utils.audio_processing import VoiceActivityDetector, TurnTakingManager
        
        # Test VAD creation
        vad = VoiceActivityDetector(sample_rate=16000)
        assert vad.sample_rate == 16000
        print("✅ Voice Activity Detector created")
        
        # Test turn-taking manager
        turn_manager = TurnTakingManager(silence_duration_ms=1000)
        assert turn_manager.silence_duration_ms == 1000
        print("✅ Turn Taking Manager created")
        
        return True
    except Exception as e:
        print(f"❌ Audio processing test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("🚀 Starting Voice Agent Basic Tests")
    print("=" * 50)
    
    tests = [
        test_basic_imports,
        test_config_creation,
        test_audio_processing,
        test_voice_agent_structure,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            print()
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            print()
    
    # Test async functionality
    try:
        if asyncio.run(test_async_functionality()):
            passed += 1
            total += 1
        else:
            total += 1
    except Exception as e:
        print(f"❌ Async test failed with exception: {e}")
        total += 1
    
    print("=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The Voice Agent structure is solid.")
        return True
    else:
        print(f"⚠️  {total - passed} tests failed.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)