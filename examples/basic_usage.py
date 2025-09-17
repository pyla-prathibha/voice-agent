"""
Basic usage example of the Voice Agent system.
"""

import asyncio
import os
from voice_agent import VoiceAgent, VoiceAgentConfig

async def example_outbound_call():
    """Example of making an outbound call with custom system prompt."""
    
    # Load configuration
    config = VoiceAgentConfig.from_env()
    
    # Create Voice Agent
    agent = VoiceAgent(config)
    
    # Set up event callbacks
    async def on_call_started(call_uuid, *args):
        print(f"✅ Call started: {call_uuid}")
    
    async def on_transcript_received(call_uuid, transcript):
        print(f"🎤 User said: {transcript}")
    
    async def on_response_generated(call_uuid, response):
        print(f"🤖 Assistant: {response}")
    
    async def on_call_ended(call_uuid, reason):
        print(f"📞 Call ended: {call_uuid} - {reason}")
    
    agent.set_callbacks(
        on_call_started=on_call_started,
        on_transcript_received=on_transcript_received,
        on_response_generated=on_response_generated,
        on_call_ended=on_call_ended
    )
    
    try:
        # Start the agent
        await agent.start()
        print("🚀 Voice Agent started")
        
        # Custom system prompt for a specific use case
        system_prompt = """You are a helpful customer service assistant for TechCorp. 
        You should be friendly, professional, and concise in your responses. 
        Help customers with their technical questions and direct them to appropriate resources when needed.
        Keep responses under 50 words when possible since this is a voice conversation."""
        
        # Make an outbound call
        call_uuid = await agent.make_call(
            to_number="+1234567890",  # Replace with actual number
            from_number="+0987654321",  # Replace with your Plivo number
            system_prompt=system_prompt
        )
        
        print(f"📞 Initiated call: {call_uuid}")
        
        # Keep the example running for demonstration
        await asyncio.sleep(60)  # Run for 1 minute
        
        # Optional: Send a message during the call
        await agent.send_message_to_call(
            call_uuid, 
            "Thank you for calling TechCorp. How can I assist you today?"
        )
        
        # Wait a bit more
        await asyncio.sleep(30)
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        # Stop the agent
        await agent.stop()
        print("🛑 Voice Agent stopped")


async def example_server_mode():
    """Example of running the Voice Agent in server mode to handle incoming calls."""
    
    # Load configuration
    config = VoiceAgentConfig.from_env()
    
    # Create Voice Agent
    agent = VoiceAgent(config)
    
    # Set up logging callbacks
    async def on_call_started(call_uuid, *args):
        print(f"📞 Incoming call: {call_uuid}")
        
        # You can customize the system prompt per call
        custom_prompt = """You are a friendly AI assistant. 
        Respond naturally and helpfully to user questions. 
        Keep your responses conversational and under 75 words."""
        
        await agent.update_system_prompt(call_uuid, custom_prompt)
    
    async def on_transcript_received(call_uuid, transcript):
        print(f"🎤 [{call_uuid[:8]}] User: {transcript}")
    
    async def on_response_generated(call_uuid, response):
        print(f"🤖 [{call_uuid[:8]}] Bot: {response}")
    
    async def on_call_ended(call_uuid, reason):
        print(f"📞 [{call_uuid[:8]}] Call ended: {reason}")
    
    agent.set_callbacks(
        on_call_started=on_call_started,
        on_transcript_received=on_transcript_received,
        on_response_generated=on_response_generated,
        on_call_ended=on_call_ended
    )
    
    try:
        # Start the agent server
        await agent.start()
        print(f"🚀 Voice Agent server running on {config.server.host}:{config.server.port}")
        print("Waiting for incoming calls...")
        print("Configure your Plivo application to point to:")
        print(f"  Answer URL: http://{config.server.host}:{config.server.port}/plivo/answer")
        print(f"  Hangup URL: http://{config.server.host}:{config.server.port}/plivo/hangup")
        
        # Keep server running
        while True:
            await asyncio.sleep(10)
            
            # Print stats every 10 seconds
            stats = agent.get_stats()
            if stats['active_sessions'] > 0:
                print(f"📊 Active sessions: {stats['active_sessions']}")
    
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    
    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        # Stop the agent
        await agent.stop()
        print("✅ Voice Agent stopped")


async def example_custom_voice_settings():
    """Example of customizing voice settings."""
    
    config = VoiceAgentConfig.from_env()
    agent = VoiceAgent(config)
    
    # Customize ElevenLabs voice settings
    agent.elevenlabs_client.configure_voice(
        stability=0.8,        # Higher stability for more consistent voice
        similarity_boost=0.9, # Higher similarity to original voice
        style=0.2,           # Slight style variation
        use_speaker_boost=True
    )
    
    # Get available voices
    voices = await agent.elevenlabs_client.get_voices()
    print("Available voices:")
    for voice in voices[:5]:  # Show first 5 voices
        print(f"  - {voice['name']} ({voice['voice_id']})")
    
    await agent.start()
    
    # Example of changing voice during runtime
    # This would typically be done in response to user preference
    # agent.config.elevenlabs.voice_id = "different_voice_id"
    
    print("Voice Agent ready with custom voice settings")
    
    # Keep running for demonstration
    await asyncio.sleep(30)
    
    await agent.stop()


def main():
    """Main function to run examples."""
    print("Voice Agent Examples")
    print("===================")
    print("1. Outbound call example")
    print("2. Server mode (handle incoming calls)")
    print("3. Custom voice settings")
    
    choice = input("Select example (1-3): ").strip()
    
    if choice == "1":
        print("\n🔄 Running outbound call example...")
        asyncio.run(example_outbound_call())
    elif choice == "2":
        print("\n🔄 Running server mode example...")
        asyncio.run(example_server_mode())
    elif choice == "3":
        print("\n🔄 Running custom voice settings example...")
        asyncio.run(example_custom_voice_settings())
    else:
        print("Invalid choice")


if __name__ == "__main__":
    # Check if environment variables are set
    required_vars = ["PLIVO_AUTH_ID", "PLIVO_AUTH_TOKEN", "ELEVENLABS_API_KEY", "OPENAI_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"  - {var}")
        print("\nPlease set these variables in your .env file or environment.")
        exit(1)
    
    main()