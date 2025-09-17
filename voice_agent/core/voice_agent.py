"""
Main Voice Agent class that orchestrates the complete voice interaction pipeline.
"""

import asyncio
from typing import Optional, Dict, Any, Callable
import structlog
from ..core.config import VoiceAgentConfig
from ..integrations.plivo_client import PlivoVoiceClient, PlivoWebServer
from ..integrations.elevenlabs_client import ElevenLabsClient
from ..integrations.openai_client import OpenAILLMClient
from ..utils.audio_processing import AudioStreamProcessor, resample_audio, normalize_audio_volume

logger = structlog.get_logger(__name__)


class VoiceAgent:
    """
    Main Voice Agent that provides real-time voice interaction using:
    - Plivo for telephony
    - ElevenLabs for STT/TTS
    - OpenAI GPT for conversational responses
    """
    
    def __init__(self, config: VoiceAgentConfig):
        """
        Initialize Voice Agent.
        
        Args:
            config: Voice Agent configuration
        """
        self.config = config
        
        # Validate configuration
        config.validate_required_fields()
        
        # Initialize components
        self.plivo_client = PlivoVoiceClient(config.plivo)
        self.elevenlabs_client = ElevenLabsClient(config.elevenlabs)
        self.openai_client = OpenAILLMClient(config.openai)
        
        # Web server for Plivo webhooks
        self.web_server = PlivoWebServer(
            self.plivo_client,
            config.server.host,
            config.server.port
        )
        
        # Audio processing
        self.audio_processor = AudioStreamProcessor(
            sample_rate=config.audio.sample_rate,
            chunk_size=config.audio.chunk_size,
            silence_duration_ms=config.audio.silence_duration_ms,
            on_turn_complete=self._handle_turn_complete
        )
        
        # Active call sessions
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        
        # Setup Plivo callbacks
        self._setup_plivo_callbacks()
        
        # Custom callbacks for extensibility
        self.on_call_started: Optional[Callable] = None
        self.on_call_ended: Optional[Callable] = None
        self.on_transcript_received: Optional[Callable] = None
        self.on_response_generated: Optional[Callable] = None
        
        logger.info("Voice Agent initialized")
    
    def _setup_plivo_callbacks(self):
        """Setup callbacks for Plivo events."""
        self.plivo_client.set_callbacks(
            on_call_initiated=self._on_call_initiated,
            on_call_answered=self._on_call_answered,
            on_call_ended=self._on_call_ended,
            on_audio_received=self._on_audio_received
        )
    
    async def start(self):
        """Start the Voice Agent server."""
        try:
            # Start web server
            self.web_server_runner = await self.web_server.start()
            
            logger.info(
                "Voice Agent started",
                host=self.config.server.host,
                port=self.config.server.port
            )
            
        except Exception as e:
            logger.error("Failed to start Voice Agent", error=str(e))
            raise
    
    async def stop(self):
        """Stop the Voice Agent server."""
        try:
            # Close active sessions
            for call_uuid in list(self.active_sessions.keys()):
                await self._end_session(call_uuid)
            
            # Stop web server
            if hasattr(self, 'web_server_runner'):
                await self.web_server.cleanup(self.web_server_runner)
            
            # Close clients
            await self.elevenlabs_client.close()
            
            logger.info("Voice Agent stopped")
            
        except Exception as e:
            logger.error("Error stopping Voice Agent", error=str(e))
    
    async def make_call(
        self,
        to_number: str,
        from_number: str,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Initiate an outbound call.
        
        Args:
            to_number: Destination phone number
            from_number: Source phone number
            system_prompt: Custom system prompt for the conversation
            
        Returns:
            Call UUID
        """
        try:
            answer_url = f"http://{self.config.server.host}:{self.config.server.port}/plivo/answer"
            
            call_uuid = await self.plivo_client.make_call(
                to_number=to_number,
                from_number=from_number,
                answer_url=answer_url
            )
            
            # Initialize session with custom system prompt if provided
            if system_prompt:
                self.active_sessions[call_uuid] = {
                    'system_prompt': system_prompt,
                    'created_at': asyncio.get_event_loop().time()
                }
            
            return call_uuid
            
        except Exception as e:
            logger.error("Failed to make call", error=str(e), to=to_number)
            raise
    
    async def hangup_call(self, call_uuid: str) -> bool:
        """
        Hang up an active call.
        
        Args:
            call_uuid: Call UUID to hang up
            
        Returns:
            True if successful
        """
        try:
            success = await self.plivo_client.hangup_call(call_uuid)
            if success:
                await self._end_session(call_uuid)
            return success
            
        except Exception as e:
            logger.error("Failed to hang up call", error=str(e), call_uuid=call_uuid)
            return False
    
    async def _on_call_initiated(self, call_uuid: str, to_number: str, from_number: str):
        """Handle call initiated event."""
        logger.info("Call initiated", call_uuid=call_uuid, to=to_number, from_=from_number)
        
        if self.on_call_started:
            await self._safe_callback(self.on_call_started, call_uuid, to_number, from_number)
    
    async def _on_call_answered(self, call_uuid: str, call_data: Dict[str, Any]):
        """Handle call answered event."""
        logger.info("Call answered", call_uuid=call_uuid)
        
        # Initialize session if not already done
        if call_uuid not in self.active_sessions:
            self.active_sessions[call_uuid] = {}
        
        self.active_sessions[call_uuid].update({
            'status': 'active',
            'answered_at': asyncio.get_event_loop().time(),
            'conversation_id': call_uuid,
            'call_data': call_data
        })
        
        if self.on_call_started:
            await self._safe_callback(self.on_call_started, call_uuid, call_data)
    
    async def _on_call_ended(self, call_uuid: str, reason: str):
        """Handle call ended event."""
        logger.info("Call ended", call_uuid=call_uuid, reason=reason)
        
        await self._end_session(call_uuid)
        
        if self.on_call_ended:
            await self._safe_callback(self.on_call_ended, call_uuid, reason)
    
    async def _on_audio_received(self, call_uuid: str, audio_data: bytes):
        """Handle audio data received from call."""
        if call_uuid not in self.active_sessions:
            logger.warning("Received audio for inactive session", call_uuid=call_uuid)
            return
        
        try:
            # Process audio chunk through the audio processor
            await self.audio_processor.process_chunk(audio_data)
            
            # Store call context for turn completion
            self.audio_processor.current_call_uuid = call_uuid
            
        except Exception as e:
            logger.error("Error processing audio", error=str(e), call_uuid=call_uuid)
    
    async def _handle_turn_complete(self, audio_data: bytes):
        """Handle completed conversation turn."""
        call_uuid = getattr(self.audio_processor, 'current_call_uuid', None)
        if not call_uuid or call_uuid not in self.active_sessions:
            logger.warning("Turn completed for unknown call")
            return
        
        session = self.active_sessions[call_uuid]
        
        try:
            # Step 1: Convert speech to text
            logger.debug("Converting speech to text", call_uuid=call_uuid)
            
            # Resample audio if needed (Plivo uses 8kHz, we might need 16kHz)
            if self.config.audio.sample_rate != 8000:
                audio_data = resample_audio(audio_data, 8000, self.config.audio.sample_rate)
            
            # Normalize audio volume
            audio_data = normalize_audio_volume(audio_data)
            
            transcript = await self.elevenlabs_client.speech_to_text(audio_data)
            
            if not transcript.strip():
                logger.debug("Empty transcript, skipping", call_uuid=call_uuid)
                return
            
            logger.info("Transcript received", call_uuid=call_uuid, transcript=transcript)
            
            if self.on_transcript_received:
                await self._safe_callback(self.on_transcript_received, call_uuid, transcript)
            
            # Step 2: Generate LLM response
            logger.debug("Generating LLM response", call_uuid=call_uuid)
            
            system_prompt = session.get('system_prompt')
            conversation_id = session['conversation_id']
            
            response_text = await self.openai_client.generate_response(
                user_input=transcript,
                conversation_id=conversation_id,
                system_prompt=system_prompt
            )
            
            if not response_text.strip():
                response_text = "I'm sorry, I didn't understand that. Could you please repeat?"
            
            logger.info("Response generated", call_uuid=call_uuid, response=response_text[:100])
            
            if self.on_response_generated:
                await self._safe_callback(self.on_response_generated, call_uuid, response_text)
            
            # Step 3: Convert text to speech
            logger.debug("Converting text to speech", call_uuid=call_uuid)
            
            response_audio = await self.elevenlabs_client.text_to_speech(response_text)
            
            if response_audio:
                # Resample for Plivo (back to 8kHz if needed)
                if self.config.audio.sample_rate != 8000:
                    response_audio = resample_audio(response_audio, self.config.audio.sample_rate, 8000)
                
                # Step 4: Send audio back to caller
                await self.plivo_client.send_audio_to_call(call_uuid, response_audio)
                
                logger.debug("Response audio sent", call_uuid=call_uuid, size=len(response_audio))
            
        except Exception as e:
            logger.error("Error handling turn completion", error=str(e), call_uuid=call_uuid)
            
            # Send error response
            try:
                error_response = "I apologize, I'm having technical difficulties. Please try again."
                error_audio = await self.elevenlabs_client.text_to_speech(error_response)
                if error_audio:
                    await self.plivo_client.send_audio_to_call(call_uuid, error_audio)
            except Exception as inner_e:
                logger.error("Failed to send error response", error=str(inner_e), call_uuid=call_uuid)
    
    async def _end_session(self, call_uuid: str):
        """End and cleanup session."""
        if call_uuid in self.active_sessions:
            session = self.active_sessions[call_uuid]
            
            # Clear conversation history
            conversation_id = session.get('conversation_id')
            if conversation_id:
                self.openai_client.remove_conversation(conversation_id)
            
            del self.active_sessions[call_uuid]
            
            logger.info("Session ended", call_uuid=call_uuid)
    
    def set_callbacks(
        self,
        on_call_started: Optional[Callable] = None,
        on_call_ended: Optional[Callable] = None,
        on_transcript_received: Optional[Callable] = None,
        on_response_generated: Optional[Callable] = None
    ):
        """
        Set custom callbacks for Voice Agent events.
        
        Args:
            on_call_started: Called when call starts
            on_call_ended: Called when call ends
            on_transcript_received: Called when transcript is received
            on_response_generated: Called when response is generated
        """
        self.on_call_started = on_call_started
        self.on_call_ended = on_call_ended
        self.on_transcript_received = on_transcript_received
        self.on_response_generated = on_response_generated
    
    def get_active_calls(self) -> Dict[str, Dict[str, Any]]:
        """Get information about active calls."""
        return {
            call_uuid: {
                **session,
                'plivo_info': self.plivo_client.get_active_calls().get(call_uuid, {})
            }
            for call_uuid, session in self.active_sessions.items()
        }
    
    def get_conversation_history(self, call_uuid: str) -> list:
        """Get conversation history for a call."""
        if call_uuid in self.active_sessions:
            conversation_id = self.active_sessions[call_uuid].get('conversation_id')
            if conversation_id:
                return self.openai_client.get_conversation_history(conversation_id)
        return []
    
    async def update_system_prompt(self, call_uuid: str, system_prompt: str):
        """
        Update system prompt for an active call.
        
        Args:
            call_uuid: Call UUID
            system_prompt: New system prompt
        """
        if call_uuid in self.active_sessions:
            self.active_sessions[call_uuid]['system_prompt'] = system_prompt
            
            conversation_id = self.active_sessions[call_uuid].get('conversation_id')
            if conversation_id and conversation_id in self.openai_client.conversations:
                self.openai_client.conversations[conversation_id].set_system_prompt(system_prompt)
                
            logger.info("System prompt updated", call_uuid=call_uuid)
    
    async def send_message_to_call(self, call_uuid: str, message: str):
        """
        Send a text message as speech to an active call.
        
        Args:
            call_uuid: Call UUID
            message: Message to send
        """
        if call_uuid not in self.active_sessions:
            raise ValueError(f"No active session for call {call_uuid}")
        
        try:
            # Convert message to speech
            audio_data = await self.elevenlabs_client.text_to_speech(message)
            
            if audio_data:
                # Send audio to call
                await self.plivo_client.send_audio_to_call(call_uuid, audio_data)
                logger.info("Message sent to call", call_uuid=call_uuid, message=message[:50])
            
        except Exception as e:
            logger.error("Failed to send message to call", error=str(e), call_uuid=call_uuid)
            raise
    
    async def _safe_callback(self, callback: Callable, *args, **kwargs):
        """Safely execute a callback, handling any exceptions."""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args, **kwargs)
            else:
                callback(*args, **kwargs)
        except Exception as e:
            logger.error("Error in callback", error=str(e))
    
    def get_stats(self) -> Dict[str, Any]:
        """Get Voice Agent statistics."""
        return {
            'active_sessions': len(self.active_sessions),
            'active_calls': len(self.plivo_client.get_active_calls()),
            'conversations': self.openai_client.get_conversation_stats(),
            'config': {
                'sample_rate': self.config.audio.sample_rate,
                'chunk_size': self.config.audio.chunk_size,
                'model': self.config.openai.model,
                'voice_id': self.config.elevenlabs.voice_id
            }
        }