# Voice Agent - Real-time Voice Interaction System

A Python-based real-time voice interaction system that combines Plivo (telephony), ElevenLabs (STT/TTS), and OpenAI GPT for intelligent conversational AI over phone calls.

## Features

- **Real-time voice activity detection** with turn-taking management
- **Plivo integration** for telephony and call handling
- **ElevenLabs STT/TTS** for high-quality speech processing
- **OpenAI GPT integration** for intelligent conversational responses
- **Async/await architecture** for high performance
- **Modular design** for easy extensibility
- **Comprehensive error handling** and logging
- **WebSocket support** for real-time audio streaming
- **Configurable voice settings** and conversation prompts

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Phone Call    │    │   Voice Agent   │    │   OpenAI GPT    │
│   (Plivo)       │◄──►│   (Orchestrator)│◄──►│   (LLM)         │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌─────────────────┐              │
         └─────────────►│  ElevenLabs     │◄─────────────┘
                        │  (STT/TTS)      │
                        └─────────────────┘
```

### Pipeline Flow

1. **Incoming Call** → Plivo receives call and establishes WebSocket connection
2. **Voice Activity Detection** → Detects speech and manages turn-taking
3. **Speech-to-Text** → Converts audio to text using ElevenLabs STT
4. **LLM Processing** → Sends transcript to OpenAI GPT for response generation
5. **Text-to-Speech** → Converts response to audio using ElevenLabs TTS
6. **Audio Streaming** → Streams generated audio back to caller via Plivo

## Installation

1. Clone the repository:
```bash
git clone https://github.com/pyla-prathibha/voice-agent.git
cd voice-agent
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables by copying and editing the example:
```bash
cp .env.example .env
# Edit .env with your API credentials
```

## Configuration

### Required Environment Variables

```bash
# Plivo credentials
PLIVO_AUTH_ID=your_plivo_auth_id
PLIVO_AUTH_TOKEN=your_plivo_auth_token

# ElevenLabs API key
ELEVENLABS_API_KEY=your_elevenlabs_api_key

# OpenAI API key
OPENAI_API_KEY=your_openai_api_key
```

### Optional Configuration

```bash
# Server settings
VOICE_AGENT_HOST=0.0.0.0
VOICE_AGENT_PORT=8080

# Audio settings
SAMPLE_RATE=16000
CHUNK_SIZE=1024
VOICE_ACTIVITY_THRESHOLD=0.5
SILENCE_DURATION_MS=1000

# LLM settings
LLM_MODEL=gpt-4
LLM_MAX_TOKENS=500
LLM_TEMPERATURE=0.7

# ElevenLabs voice
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM
```

## Quick Start

### 1. Server Mode (Handle Incoming Calls)

```python
import asyncio
from voice_agent import VoiceAgent, VoiceAgentConfig

async def main():
    # Load configuration
    config = VoiceAgentConfig.from_env()
    
    # Create and start agent
    agent = VoiceAgent(config)
    await agent.start()
    
    print(f"Voice Agent running on {config.server.host}:{config.server.port}")
    
    # Configure your Plivo application to point to:
    # Answer URL: http://your-server:8080/plivo/answer
    # Hangup URL: http://your-server:8080/plivo/hangup
    
    # Keep server running
    await asyncio.sleep(3600)  # Run for 1 hour
    
    await agent.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

### 2. Outbound Calls

```python
import asyncio
from voice_agent import VoiceAgent, VoiceAgentConfig

async def make_call():
    config = VoiceAgentConfig.from_env()
    agent = VoiceAgent(config)
    
    await agent.start()
    
    # Make outbound call with custom prompt
    call_uuid = await agent.make_call(
        to_number="+1234567890",
        from_number="+0987654321",
        system_prompt="You are a helpful customer service assistant."
    )
    
    print(f"Call initiated: {call_uuid}")
    
    # Wait for call to complete
    await asyncio.sleep(120)
    
    await agent.stop()

asyncio.run(make_call())
```

### 3. Custom Event Handling

```python
async def on_transcript_received(call_uuid, transcript):
    print(f"User said: {transcript}")

async def on_response_generated(call_uuid, response):
    print(f"AI responded: {response}")

# Set callbacks
agent.set_callbacks(
    on_transcript_received=on_transcript_received,
    on_response_generated=on_response_generated
)
```

## Advanced Usage

### Custom System Prompts

```python
# Set system prompt when making a call
call_uuid = await agent.make_call(
    to_number="+1234567890",
    from_number="+0987654321",
    system_prompt="""You are a medical appointment scheduler. 
    Help patients schedule, reschedule, or cancel appointments.
    Be professional and empathetic. Ask for necessary information 
    like patient name, preferred date/time, and reason for visit."""
)

# Update system prompt during a call
await agent.update_system_prompt(
    call_uuid, 
    "You are now helping with technical support issues."
)
```

### Custom Voice Settings

```python
# Configure ElevenLabs voice settings
agent.elevenlabs_client.configure_voice(
    stability=0.8,        # Higher stability for consistent voice
    similarity_boost=0.9, # Higher similarity to original voice
    style=0.2,           # Slight style variation
    use_speaker_boost=True
)

# Get available voices
voices = await agent.elevenlabs_client.get_voices()
for voice in voices:
    print(f"{voice['name']}: {voice['voice_id']}")
```

### Monitoring and Statistics

```python
# Get real-time statistics
stats = agent.get_stats()
print(f"Active sessions: {stats['active_sessions']}")
print(f"Total conversations: {stats['conversations']['total_conversations']}")

# Get active calls
active_calls = agent.get_active_calls()
for call_uuid, call_info in active_calls.items():
    print(f"Call {call_uuid}: {call_info['status']}")

# Get conversation history
history = agent.get_conversation_history(call_uuid)
for message in history:
    print(f"{message['role']}: {message['content']}")
```

## API Reference

### VoiceAgent Class

#### Methods

- `__init__(config: VoiceAgentConfig)` - Initialize the voice agent
- `async start()` - Start the voice agent server
- `async stop()` - Stop the voice agent server
- `async make_call(to_number, from_number, system_prompt=None)` - Make outbound call
- `async hangup_call(call_uuid)` - Hang up active call
- `async send_message_to_call(call_uuid, message)` - Send message to active call
- `async update_system_prompt(call_uuid, system_prompt)` - Update conversation prompt
- `set_callbacks(**callbacks)` - Set event callbacks
- `get_active_calls()` - Get active call information
- `get_conversation_history(call_uuid)` - Get conversation history
- `get_stats()` - Get system statistics

#### Events

- `on_call_started(call_uuid, *args)` - Called when call starts
- `on_call_ended(call_uuid, reason)` - Called when call ends
- `on_transcript_received(call_uuid, transcript)` - Called when speech is transcribed
- `on_response_generated(call_uuid, response)` - Called when AI response is generated

### Configuration Classes

- `VoiceAgentConfig` - Main configuration
- `PlivoConfig` - Plivo telephony settings
- `ElevenLabsConfig` - ElevenLabs STT/TTS settings
- `OpenAIConfig` - OpenAI LLM settings
- `AudioConfig` - Audio processing settings
- `ServerConfig` - Web server settings

## Testing

Run the test suite:

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run tests
pytest tests/

# Run with coverage
pytest tests/ --cov=voice_agent
```

## Deployment

### Production Deployment

1. **Environment Setup**:
   ```bash
   # Use production environment variables
   export VOICE_AGENT_HOST=0.0.0.0
   export VOICE_AGENT_PORT=80
   ```

2. **Process Management**:
   ```bash
   # Using systemd, supervisor, or similar
   python main.py
   ```

3. **Reverse Proxy** (nginx example):
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;
       
       location / {
           proxy_pass http://localhost:8080;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection 'upgrade';
           proxy_set_header Host $host;
           proxy_cache_bypass $http_upgrade;
       }
   }
   ```

4. **Plivo Configuration**:
   - Set Answer URL: `http://your-domain.com/plivo/answer`
   - Set Hangup URL: `http://your-domain.com/plivo/hangup`

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8080
CMD ["python", "main.py"]
```

## Roadmap

### Version 1.0 (Current) ✅
- Basic voice interaction pipeline
- Plivo + ElevenLabs + OpenAI integration
- Real-time audio processing
- Turn-taking and VAD

### Version 2.0 (Planned)
- **Prompt Customization**:
  - Dynamic prompt templates
  - Context-aware prompts
  - Multi-language support
  - Conversation templates

### Version 3.0 (Planned)
- **Tool Calls & Integration**:
  - Function calling support
  - External API integrations
  - Database queries
  - Calendar/scheduling integration
  - CRM integration

### Version 4.0 (Planned)
- **Optimization & Scaling**:
  - Response caching
  - Model fine-tuning
  - Load balancing
  - Analytics and insights
  - Voice cloning
  - Emotion detection

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and add tests
4. Run tests: `pytest`
5. Commit your changes: `git commit -am 'Add feature'`
6. Push to the branch: `git push origin feature-name`
7. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For questions, issues, or contributions, please:

1. Check the [Issues](https://github.com/pyla-prathibha/voice-agent/issues) page
2. Create a new issue if needed
3. Join our discussions

## Acknowledgments

- [Plivo](https://www.plivo.com/) for telephony services
- [ElevenLabs](https://elevenlabs.io/) for STT/TTS capabilities
- [OpenAI](https://openai.com/) for LLM integration
- [WebRTC VAD](https://github.com/wiseman/py-webrtcvad) for voice activity detection