"""
Plivo telephony integration for real-time voice calls.
"""

import asyncio
import json
from typing import AsyncGenerator, Callable, Optional, Dict, Any

try:
    from aiohttp import web, WSMsgType
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    web = None
    WSMsgType = None

try:
    import plivo
    PLIVO_AVAILABLE = True
except ImportError:
    PLIVO_AVAILABLE = False
    plivo = None

import structlog
from ..core.config import PlivoConfig

logger = structlog.get_logger(__name__)


class PlivoVoiceClient:
    """Plivo client for handling voice calls and real-time audio streaming."""
    
    def __init__(self, config: PlivoConfig):
        """
        Initialize Plivo client.
        
        Args:
            config: Plivo configuration
        """
        self.config = config
        if PLIVO_AVAILABLE:
            self.client = plivo.RestClient(config.auth_id, config.auth_token)
        else:
            self.client = None
        self.active_calls: Dict[str, Dict[str, Any]] = {}
        
        # Callbacks
        self.on_call_initiated: Optional[Callable] = None
        self.on_call_answered: Optional[Callable] = None
        self.on_call_ended: Optional[Callable] = None
        self.on_audio_received: Optional[Callable] = None
        
    def set_callbacks(
        self,
        on_call_initiated: Optional[Callable] = None,
        on_call_answered: Optional[Callable] = None,
        on_call_ended: Optional[Callable] = None,
        on_audio_received: Optional[Callable] = None
    ):
        """Set event callbacks."""
        self.on_call_initiated = on_call_initiated
        self.on_call_answered = on_call_answered
        self.on_call_ended = on_call_ended
        self.on_audio_received = on_audio_received
    
    async def make_call(
        self,
        to_number: str,
        from_number: str,
        answer_url: str,
        **kwargs
    ) -> str:
        """
        Initiate an outbound call.
        
        Args:
            to_number: Destination phone number
            from_number: Source phone number
            answer_url: URL to handle call events
            **kwargs: Additional call parameters
            
        Returns:
            Call UUID
        """
        try:
            call = self.client.calls.create(
                from_=from_number,
                to_=to_number,
                answer_url=answer_url,
                **kwargs
            )
            
            call_uuid = call.call_uuid
            self.active_calls[call_uuid] = {
                'to': to_number,
                'from': from_number,
                'status': 'initiated',
                'start_time': asyncio.get_event_loop().time()
            }
            
            logger.info("Call initiated", call_uuid=call_uuid, to=to_number)
            
            if self.on_call_initiated:
                await self._safe_callback(self.on_call_initiated, call_uuid, to_number, from_number)
            
            return call_uuid
            
        except Exception as e:
            logger.error("Failed to initiate call", error=str(e), to=to_number)
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
            self.client.calls.hangup(call_uuid)
            
            if call_uuid in self.active_calls:
                self.active_calls[call_uuid]['status'] = 'ended'
                del self.active_calls[call_uuid]
            
            logger.info("Call hung up", call_uuid=call_uuid)
            
            if self.on_call_ended:
                await self._safe_callback(self.on_call_ended, call_uuid, 'hangup')
            
            return True
            
        except Exception as e:
            logger.error("Failed to hang up call", error=str(e), call_uuid=call_uuid)
            return False
    
    def get_call_xml_response(self, websocket_url: str) -> str:
        """
        Generate XML response for call handling with WebSocket streaming.
        
        Args:
            websocket_url: URL for WebSocket audio streaming
            
        Returns:
            XML response string
        """
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak>Hello! I'm your voice assistant. Please start speaking.</Speak>
    <Stream bidirectional="true" keepCallAlive="true">
        <Parameter name="address" value="{websocket_url}" />
        <Parameter name="codec" value="mulaw" />
        <Parameter name="sample_rate" value="8000" />
    </Stream>
</Response>"""
    
    async def handle_call_event(self, request: web.Request) -> web.Response:
        """
        Handle Plivo call events (webhooks).
        
        Args:
            request: HTTP request from Plivo
            
        Returns:
            HTTP response
        """
        try:
            data = await request.post()
            event = data.get('Event', '')
            call_uuid = data.get('CallUUID', '')
            
            logger.info("Call event received", event=event, call_uuid=call_uuid, data=dict(data))
            
            if event == 'StartApp':
                # Call answered and app started
                if call_uuid in self.active_calls:
                    self.active_calls[call_uuid]['status'] = 'answered'
                
                if self.on_call_answered:
                    await self._safe_callback(self.on_call_answered, call_uuid, dict(data))
                
                # Return XML to start streaming
                websocket_url = f"wss://{request.host}/ws/audio/{call_uuid}"
                xml_response = self.get_call_xml_response(websocket_url)
                
                return web.Response(
                    text=xml_response,
                    content_type='application/xml'
                )
            
            elif event == 'EndApp':
                # Call ended
                if call_uuid in self.active_calls:
                    self.active_calls[call_uuid]['status'] = 'ended'
                    del self.active_calls[call_uuid]
                
                if self.on_call_ended:
                    await self._safe_callback(self.on_call_ended, call_uuid, 'ended')
            
            return web.Response(text='OK')
            
        except Exception as e:
            logger.error("Error handling call event", error=str(e))
            return web.Response(text='Error', status=500)
    
    async def handle_audio_websocket(self, request: web.Request) -> web.WebSocketResponse:
        """
        Handle WebSocket connection for real-time audio streaming.
        
        Args:
            request: WebSocket request
            
        Returns:
            WebSocket response
        """
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        call_uuid = request.match_info.get('call_uuid', '')
        logger.info("Audio WebSocket connected", call_uuid=call_uuid)
        
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    # Handle control messages
                    try:
                        data = json.loads(msg.data)
                        await self._handle_websocket_control(ws, call_uuid, data)
                    except json.JSONDecodeError:
                        logger.warning("Invalid JSON in WebSocket message", data=msg.data)
                
                elif msg.type == WSMsgType.BINARY:
                    # Handle audio data
                    audio_data = msg.data
                    
                    if self.on_audio_received:
                        await self._safe_callback(self.on_audio_received, call_uuid, audio_data)
                
                elif msg.type == WSMsgType.ERROR:
                    logger.error("WebSocket error", error=ws.exception())
                    break
        
        except Exception as e:
            logger.error("Error in audio WebSocket", error=str(e), call_uuid=call_uuid)
        
        finally:
            logger.info("Audio WebSocket disconnected", call_uuid=call_uuid)
        
        return ws
    
    async def send_audio_to_call(self, call_uuid: str, audio_data: bytes):
        """
        Send audio data to an active call via WebSocket.
        
        Args:
            call_uuid: Call UUID
            audio_data: Raw audio data to send
        """
        # This would be implemented to send audio through the WebSocket
        # For now, we'll store it for the WebSocket handler to pick up
        if call_uuid in self.active_calls:
            if 'outbound_audio_queue' not in self.active_calls[call_uuid]:
                self.active_calls[call_uuid]['outbound_audio_queue'] = asyncio.Queue()
            
            await self.active_calls[call_uuid]['outbound_audio_queue'].put(audio_data)
    
    async def _handle_websocket_control(self, ws: web.WebSocketResponse, call_uuid: str, data: Dict[str, Any]):
        """Handle WebSocket control messages."""
        message_type = data.get('type', '')
        
        if message_type == 'start':
            logger.info("Audio streaming started", call_uuid=call_uuid)
        elif message_type == 'stop':
            logger.info("Audio streaming stopped", call_uuid=call_uuid)
        elif message_type == 'error':
            logger.error("Audio streaming error", call_uuid=call_uuid, error=data.get('error'))
    
    async def _safe_callback(self, callback: Callable, *args, **kwargs):
        """Safely execute a callback, handling any exceptions."""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args, **kwargs)
            else:
                callback(*args, **kwargs)
        except Exception as e:
            logger.error("Error in callback", error=str(e))
    
    def get_active_calls(self) -> Dict[str, Dict[str, Any]]:
        """Get information about active calls."""
        return self.active_calls.copy()
    
    def is_call_active(self, call_uuid: str) -> bool:
        """Check if a call is active."""
        return call_uuid in self.active_calls and self.active_calls[call_uuid]['status'] in ['initiated', 'answered']


class PlivoWebServer:
    """Web server for handling Plivo webhooks and WebSocket connections."""
    
    def __init__(self, plivo_client: PlivoVoiceClient, host: str = '0.0.0.0', port: int = 8080):
        """
        Initialize web server.
        
        Args:
            plivo_client: Plivo client instance
            host: Server host
            port: Server port
        """
        self.plivo_client = plivo_client
        self.host = host
        self.port = port
        self.app = web.Application()
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup web server routes."""
        self.app.router.add_post('/plivo/answer', self.plivo_client.handle_call_event)
        self.app.router.add_post('/plivo/hangup', self.plivo_client.handle_call_event)
        self.app.router.add_get('/ws/audio/{call_uuid}', self.plivo_client.handle_audio_websocket)
        
        # Health check endpoint
        self.app.router.add_get('/health', self._health_check)
    
    async def _health_check(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        return web.Response(json={'status': 'healthy', 'active_calls': len(self.plivo_client.active_calls)})
    
    async def start(self):
        """Start the web server."""
        runner = web.AppRunner(self.app)
        await runner.setup()
        
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        
        logger.info("Plivo web server started", host=self.host, port=self.port)
        return runner
    
    async def cleanup(self, runner: web.AppRunner):
        """Cleanup web server resources."""
        await runner.cleanup()