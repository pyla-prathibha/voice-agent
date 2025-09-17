"""
OpenAI integration for LLM-powered conversational responses.
"""

import asyncio
from typing import List, Dict, Any, Optional, AsyncGenerator

try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    AsyncOpenAI = None

import structlog
from ..core.config import OpenAIConfig

logger = structlog.get_logger(__name__)


class ConversationContext:
    """Manages conversation context and history."""
    
    def __init__(self, max_history: int = 10, system_prompt: Optional[str] = None):
        """
        Initialize conversation context.
        
        Args:
            max_history: Maximum number of conversation turns to keep
            system_prompt: System prompt for the assistant
        """
        self.max_history = max_history
        self.messages: List[Dict[str, str]] = []
        
        # Default system prompt for voice assistant
        if system_prompt is None:
            system_prompt = """You are a helpful voice assistant. You should:
1. Provide concise, conversational responses suitable for speech
2. Keep responses brief and to the point (under 100 words when possible)
3. Be friendly and natural in your communication style
4. Ask clarifying questions when needed
5. Handle voice conversation context appropriately"""
        
        if system_prompt:
            self.messages.append({"role": "system", "content": system_prompt})
    
    def add_user_message(self, content: str):
        """Add user message to conversation."""
        if content.strip():
            self.messages.append({"role": "user", "content": content.strip()})
            self._trim_history()
    
    def add_assistant_message(self, content: str):
        """Add assistant message to conversation."""
        if content.strip():
            self.messages.append({"role": "assistant", "content": content.strip()})
            self._trim_history()
    
    def _trim_history(self):
        """Trim conversation history to max_history, keeping system message."""
        if len(self.messages) <= self.max_history + 1:  # +1 for system message
            return
        
        # Keep system message (first) and recent messages
        system_msg = self.messages[0] if self.messages[0]["role"] == "system" else None
        recent_messages = self.messages[-(self.max_history):]
        
        self.messages = ([system_msg] if system_msg else []) + recent_messages
    
    def get_messages(self) -> List[Dict[str, str]]:
        """Get current conversation messages."""
        return self.messages.copy()
    
    def clear(self, keep_system: bool = True):
        """Clear conversation history."""
        if keep_system and self.messages and self.messages[0]["role"] == "system":
            self.messages = [self.messages[0]]
        else:
            self.messages = []
    
    def set_system_prompt(self, prompt: str):
        """Update system prompt."""
        # Remove existing system message if present
        if self.messages and self.messages[0]["role"] == "system":
            self.messages.pop(0)
        
        # Add new system message at the beginning
        if prompt.strip():
            self.messages.insert(0, {"role": "system", "content": prompt.strip()})


class OpenAILLMClient:
    """OpenAI client for LLM conversational responses."""
    
    def __init__(self, config: OpenAIConfig):
        """
        Initialize OpenAI client.
        
        Args:
            config: OpenAI configuration
        """
        self.config = config
        if OPENAI_AVAILABLE:
            self.client = AsyncOpenAI(api_key=config.api_key)
        else:
            self.client = None
        self.conversations: Dict[str, ConversationContext] = {}
    
    def get_conversation(
        self,
        conversation_id: str,
        system_prompt: Optional[str] = None,
        max_history: int = 10
    ) -> ConversationContext:
        """
        Get or create conversation context.
        
        Args:
            conversation_id: Unique identifier for conversation
            system_prompt: System prompt (used only when creating new conversation)
            max_history: Maximum conversation history length
            
        Returns:
            ConversationContext instance
        """
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = ConversationContext(max_history, system_prompt)
        
        return self.conversations[conversation_id]
    
    async def generate_response(
        self,
        user_input: str,
        conversation_id: str,
        system_prompt: Optional[str] = None,
        streaming: bool = False
    ) -> str | AsyncGenerator[str, None]:
        """
        Generate LLM response to user input.
        
        Args:
            user_input: User's input text
            conversation_id: Conversation identifier
            system_prompt: Optional system prompt override
            streaming: Whether to return streaming response
            
        Returns:
            Generated response text or async generator of response chunks
        """
        if not user_input.strip():
            return "" if not streaming else self._empty_stream()
        
        conversation = self.get_conversation(conversation_id, system_prompt)
        
        # Update system prompt if provided
        if system_prompt:
            conversation.set_system_prompt(system_prompt)
        
        # Add user message
        conversation.add_user_message(user_input)
        
        try:
            if streaming:
                return self._generate_streaming_response(conversation)
            else:
                return await self._generate_complete_response(conversation)
        
        except Exception as e:
            logger.error("Error generating LLM response", error=str(e), user_input=user_input[:100])
            error_response = "I apologize, but I'm having trouble processing your request right now. Could you please try again?"
            
            if not streaming:
                return error_response
            else:
                return self._error_stream(error_response)
    
    async def _generate_complete_response(self, conversation: ConversationContext) -> str:
        """Generate complete response."""
        response = await self.client.chat.completions.create(
            model=self.config.model,
            messages=conversation.get_messages(),
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature
        )
        
        assistant_message = response.choices[0].message.content
        if assistant_message:
            conversation.add_assistant_message(assistant_message)
            logger.info("LLM response generated", response_length=len(assistant_message))
            return assistant_message
        
        return ""
    
    async def _generate_streaming_response(self, conversation: ConversationContext) -> AsyncGenerator[str, None]:
        """Generate streaming response."""
        full_response = ""
        
        try:
            stream = await self.client.chat.completions.create(
                model=self.config.model,
                messages=conversation.get_messages(),
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                stream=True
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    yield content
            
            # Add complete response to conversation history
            if full_response:
                conversation.add_assistant_message(full_response)
                logger.info("Streaming LLM response completed", response_length=len(full_response))
        
        except Exception as e:
            logger.error("Error in streaming response", error=str(e))
            yield "I apologize, but I'm having trouble processing your request."
    
    async def _empty_stream(self) -> AsyncGenerator[str, None]:
        """Return empty async generator."""
        return
        yield  # Make this a generator
    
    async def _error_stream(self, error_message: str) -> AsyncGenerator[str, None]:
        """Return error message as stream."""
        yield error_message
    
    def clear_conversation(self, conversation_id: str, keep_system: bool = True):
        """
        Clear conversation history.
        
        Args:
            conversation_id: Conversation to clear
            keep_system: Whether to keep system prompt
        """
        if conversation_id in self.conversations:
            self.conversations[conversation_id].clear(keep_system)
    
    def remove_conversation(self, conversation_id: str):
        """Remove conversation completely."""
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]
    
    def get_conversation_history(self, conversation_id: str) -> List[Dict[str, str]]:
        """Get conversation history."""
        if conversation_id in self.conversations:
            return self.conversations[conversation_id].get_messages()
        return []
    
    async def analyze_intent(self, user_input: str) -> Dict[str, Any]:
        """
        Analyze user intent for more sophisticated handling.
        
        Args:
            user_input: User's input text
            
        Returns:
            Intent analysis result
        """
        if not user_input.strip():
            return {"intent": "unclear", "confidence": 0.0, "entities": []}
        
        try:
            intent_prompt = f"""Analyze the following user input and determine:
1. The primary intent (e.g., question, request, greeting, goodbye, complaint, compliment)
2. Confidence level (0.0-1.0)
3. Any important entities or topics mentioned

User input: "{user_input}"

Respond in JSON format with keys: intent, confidence, entities, summary"""
            
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",  # Use faster model for intent analysis
                messages=[
                    {"role": "system", "content": "You are an intent analysis system. Respond only with valid JSON."},
                    {"role": "user", "content": intent_prompt}
                ],
                max_tokens=200,
                temperature=0.1
            )
            
            import json
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            logger.error("Error analyzing intent", error=str(e))
            return {
                "intent": "unclear",
                "confidence": 0.0,
                "entities": [],
                "summary": "Unable to analyze"
            }
    
    async def generate_contextual_response(
        self,
        user_input: str,
        conversation_id: str,
        context: Dict[str, Any] = None,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Generate response with additional context information.
        
        Args:
            user_input: User's input text
            conversation_id: Conversation identifier
            context: Additional context information
            system_prompt: Optional system prompt override
            
        Returns:
            Generated response
        """
        # Enhance system prompt with context if provided
        if context and system_prompt:
            context_info = "\n\nAdditional context:\n"
            for key, value in context.items():
                context_info += f"- {key}: {value}\n"
            system_prompt += context_info
        
        return await self.generate_response(user_input, conversation_id, system_prompt)
    
    def get_active_conversations(self) -> List[str]:
        """Get list of active conversation IDs."""
        return list(self.conversations.keys())
    
    def get_conversation_stats(self) -> Dict[str, Any]:
        """Get statistics about conversations."""
        return {
            "total_conversations": len(self.conversations),
            "total_messages": sum(len(conv.messages) for conv in self.conversations.values()),
            "active_conversations": list(self.conversations.keys())
        }