#!/usr/bin/env python3
"""
Quick start example for the Voice Agent.
This demonstrates how to run the system with minimal setup.
"""

import asyncio
import sys
import os
from voice_agent import VoiceAgent, VoiceAgentConfig

async def quick_start_demo():
    """Quick demonstration of the Voice Agent."""
    
    print("🎤 Voice Agent Quick Start Demo")
    print("=" * 40)
    
    # Check if environment variables are set
    required_vars = ["PLIVO_AUTH_ID", "PLIVO_AUTH_TOKEN", "ELEVENLABS_API_KEY", "OPENAI_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"  - {var}")
        print("\nPlease set these in your .env file or environment.")
        print("See .env.example for a template.")
        return False
    
    try:
        # Load configuration
        config = VoiceAgentConfig.from_env()
        print(f"✅ Configuration loaded")
        print(f"   - Server: {config.server.host}:{config.server.port}")
        print(f"   - Audio: {config.audio.sample_rate}Hz")
        print(f"   - Model: {config.openai.model}")
        
        # Create Voice Agent
        agent = VoiceAgent(config)
        
        # Set up event logging
        async def on_call_started(call_uuid, *args):
            print(f"\n📞 Call started: {call_uuid}")
        
        async def on_transcript_received(call_uuid, transcript):
            print(f"🎤 [{call_uuid[:8]}] User: {transcript}")
        
        async def on_response_generated(call_uuid, response):
            print(f"🤖 [{call_uuid[:8]}] Assistant: {response}")
        
        async def on_call_ended(call_uuid, reason):
            print(f"📞 [{call_uuid[:8]}] Call ended: {reason}\n")
        
        agent.set_callbacks(
            on_call_started=on_call_started,
            on_transcript_received=on_transcript_received,
            on_response_generated=on_response_generated,
            on_call_ended=on_call_ended
        )
        
        # Start the agent
        await agent.start()
        print(f"\n🚀 Voice Agent is running!")
        print(f"   Server URL: http://{config.server.host}:{config.server.port}")
        print(f"   Health check: http://{config.server.host}:{config.server.port}/health")
        
        print("\n📋 Plivo Configuration:")
        print(f"   Answer URL: http://your-domain:8080/plivo/answer")
        print(f"   Hangup URL: http://your-domain:8080/plivo/hangup")
        print(f"   WebSocket URL: wss://your-domain:8080/ws/audio/{{call_uuid}}")
        
        print("\n🎯 What you can do:")
        print("   1. Configure your Plivo application with the URLs above")
        print("   2. Make calls to your Plivo number")
        print("   3. Watch the console for real-time conversation logs")
        print("   4. The AI will respond to voice input automatically")
        
        print("\n⏸️  Press Ctrl+C to stop the server")
        
        # Keep running until interrupted  
        try:
            while True:
                await asyncio.sleep(10)
                
                # Show stats every 30 seconds
                stats = agent.get_stats()
                if stats['active_sessions'] > 0:
                    print(f"📊 Active sessions: {stats['active_sessions']}")
        
        except KeyboardInterrupt:
            print("\n🛑 Shutting down Voice Agent...")
        
        finally:
            await agent.stop()
            print("✅ Voice Agent stopped successfully")
            
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def make_test_call():
    """Example of making an outbound test call."""
    
    print("📞 Test Call Example")
    print("=" * 30)
    
    # Get phone numbers from user
    to_number = input("Enter destination number (e.g., +1234567890): ").strip()
    from_number = input("Enter your Plivo number (e.g., +0987654321): ").strip()
    
    if not to_number or not from_number:
        print("❌ Both phone numbers are required")
        return
    
    try:
        config = VoiceAgentConfig.from_env()
        agent = VoiceAgent(config)
        
        await agent.start()
        print("🚀 Voice Agent started for test call")
        
        # Custom system prompt for test
        system_prompt = """You are a friendly AI assistant making a test call. 
        Introduce yourself briefly and ask how you can help today. 
        Keep responses short and conversational since this is a voice call."""
        
        call_uuid = await agent.make_call(
            to_number=to_number,
            from_number=from_number,
            system_prompt=system_prompt
        )
        
        print(f"📞 Test call initiated: {call_uuid}")
        print("🎯 Call will connect shortly. Speak naturally when answered.")
        
        # Let call run for 2 minutes
        await asyncio.sleep(120)
        
        # End the call
        await agent.hangup_call(call_uuid)
        print("📞 Test call ended")
        
        await agent.stop()
        
    except Exception as e:
        print(f"❌ Test call failed: {e}")

def main():
    """Main entry point with menu."""
    
    print("🎤 Voice Agent - Choose an option:")
    print("1. Start server (handle incoming calls)")
    print("2. Make test call (outbound)")
    print("3. Exit")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == "1":
        print("\n🚀 Starting Voice Agent server...")
        asyncio.run(quick_start_demo())
    elif choice == "2":
        print("\n📞 Making test call...")
        asyncio.run(make_test_call())
    elif choice == "3":
        print("👋 Goodbye!")
    else:
        print("❌ Invalid choice")

if __name__ == "__main__":
    main()