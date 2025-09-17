"""
Main entry point for the Voice Agent application.
"""

import asyncio
import signal
import sys
from typing import Optional
import structlog
from voice_agent import VoiceAgent, VoiceAgentConfig

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="ISO"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO level
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


class VoiceAgentServer:
    """Voice Agent server application."""
    
    def __init__(self):
        self.voice_agent: Optional[VoiceAgent] = None
        self.shutdown_event = asyncio.Event()
    
    async def start(self):
        """Start the Voice Agent server."""
        try:
            # Load configuration from environment
            config = VoiceAgentConfig.from_env()
            
            # Initialize Voice Agent
            self.voice_agent = VoiceAgent(config)
            
            # Set up callbacks for logging
            self.voice_agent.set_callbacks(
                on_call_started=self.on_call_started,
                on_call_ended=self.on_call_ended,
                on_transcript_received=self.on_transcript_received,
                on_response_generated=self.on_response_generated
            )
            
            # Start the Voice Agent
            await self.voice_agent.start()
            
            logger.info(
                "Voice Agent server started successfully",
                host=config.server.host,
                port=config.server.port
            )
            
            # Wait for shutdown signal
            await self.shutdown_event.wait()
            
        except Exception as e:
            logger.error("Failed to start Voice Agent server", error=str(e))
            raise
        
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the Voice Agent server."""
        if self.voice_agent:
            try:
                await self.voice_agent.stop()
                logger.info("Voice Agent server stopped")
            except Exception as e:
                logger.error("Error stopping Voice Agent", error=str(e))
    
    def shutdown(self):
        """Signal shutdown."""
        logger.info("Shutdown signal received")
        self.shutdown_event.set()
    
    async def on_call_started(self, call_uuid: str, *args):
        """Handle call started event."""
        logger.info("Call started", call_uuid=call_uuid, args=args)
    
    async def on_call_ended(self, call_uuid: str, reason: str):
        """Handle call ended event."""
        logger.info("Call ended", call_uuid=call_uuid, reason=reason)
    
    async def on_transcript_received(self, call_uuid: str, transcript: str):
        """Handle transcript received event."""
        logger.info("Transcript received", call_uuid=call_uuid, transcript=transcript)
    
    async def on_response_generated(self, call_uuid: str, response: str):
        """Handle response generated event."""
        logger.info("Response generated", call_uuid=call_uuid, response=response[:100])


async def main():
    """Main application entry point."""
    server = VoiceAgentServer()
    
    # Setup signal handlers
    def signal_handler():
        server.shutdown()
    
    # Handle shutdown signals
    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, lambda s, f: signal_handler())
    
    try:
        await server.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error("Application error", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application interrupted")
    except Exception as e:
        logger.error("Fatal error", error=str(e))
        sys.exit(1)