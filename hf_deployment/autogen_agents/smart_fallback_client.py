"""
Smart Fallback Client for AutoGen 0.6+
Automatically switches between Groq and Hugging Face APIs based on availability and rate limits
"""

import os
import logging
import time
from typing import Dict, Any, List, Optional, Sequence
from autogen_core.models import ChatCompletionClient, ModelFamily, ModelInfo
from autogen_agentchat.messages import BaseChatMessage, TextMessage
from autogen_core.models import SystemMessage, UserMessage, AssistantMessage
from autogen_core import CancellationToken
from dotenv import load_dotenv

# Import our custom clients
from .groq_client import create_groq_client, GroqChatCompletionClient
from .hf_client import create_hf_client, HuggingFaceChatCompletionClient

load_dotenv()

class SmartFallbackClient(ChatCompletionClient):
    """
    Smart client that automatically falls back from Groq to Hugging Face
    when rate limits are hit or other errors occur
    """
    
    def __init__(self):
        self.primary_client = None
        self.fallback_client = None
        self.current_client = None
        self.fallback_active = False
        self.last_fallback_time = 0
        self.fallback_reset_interval = 300  # 5 minutes
        
        # Initialize clients
        self._initialize_clients()
        
        # Model info (combined capabilities)
        self._model_info = ModelInfo(
            vision=False,
            function_calling=True,  # Groq supports this
            json_output=True,       # Groq supports this
            family=ModelFamily.UNKNOWN,
            structured_output=False
        )
    
    def _initialize_clients(self):
        """Initialize primary and fallback clients"""
        try:
            # Primary: Groq (faster, but has rate limits)
            self.primary_client = create_groq_client()
            if self.primary_client:
                logging.info("✅ Primary client (Groq) initialized successfully")
            else:
                logging.warning("⚠️ Primary client (Groq) not available")
            
            # Fallback: Hugging Face (more stable, higher limits)
            self.fallback_client = create_hf_client()
            if self.fallback_client:
                logging.info("✅ Fallback client (Hugging Face) initialized successfully")
            else:
                logging.warning("⚠️ Fallback client (Hugging Face) not available")
            
            # Set current client
            self.current_client = self.primary_client or self.fallback_client
            
            if not self.current_client:
                raise ValueError("No API clients available. Please check your API keys.")
                
        except Exception as e:
            logging.error(f"Failed to initialize clients: {e}")
            raise
    
    def _should_reset_fallback(self) -> bool:
        """Check if we should try the primary client again"""
        if not self.fallback_active:
            return False
        
        current_time = time.time()
        return (current_time - self.last_fallback_time) > self.fallback_reset_interval
    
    def _activate_fallback(self, reason: str):
        """Activate fallback client"""
        if self.fallback_client and not self.fallback_active:
            logging.warning(f"🔄 Switching to fallback client (Hugging Face). Reason: {reason}")
            self.current_client = self.fallback_client
            self.fallback_active = True
            self.last_fallback_time = time.time()
        elif not self.fallback_client:
            logging.error("❌ No fallback client available!")
            raise Exception("Primary client failed and no fallback available")
    
    def _try_primary_client(self):
        """Try to switch back to primary client"""
        if self.primary_client and self.fallback_active:
            logging.info("🔄 Attempting to switch back to primary client (Groq)")
            self.current_client = self.primary_client
            self.fallback_active = False
    
    @property
    def model_info(self) -> ModelInfo:
        return self._model_info
    
    @property
    def capabilities(self) -> Dict[str, Any]:
        return {
            "vision": False,
            "function_calling": True,
            "json_output": True,
            "structured_output": False
        }
    
    def count_tokens(self, messages: Sequence[BaseChatMessage], **kwargs) -> int:
        """Estimate token count using current client"""
        if self.current_client:
            return self.current_client.count_tokens(messages, **kwargs)
        return 0
    
    def remaining_tokens(self, messages: Sequence[BaseChatMessage], **kwargs) -> int:
        """Estimate remaining tokens using current client"""
        if self.current_client:
            return self.current_client.remaining_tokens(messages, **kwargs)
        return 0
    
    @property
    def total_usage(self) -> Dict[str, int]:
        """Return total usage statistics"""
        if self.current_client:
            return self.current_client.total_usage
        return {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0}
    
    @property
    def actual_usage(self) -> Dict[str, int]:
        """Return actual usage statistics"""
        if self.current_client:
            return self.current_client.actual_usage
        return {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0}
    
    async def create_stream(self, messages: Sequence[BaseChatMessage], cancellation_token: CancellationToken, **kwargs):
        """Create streaming response with fallback"""
        response = await self.create(messages, cancellation_token, **kwargs)
        yield response
    
    async def close(self):
        """Close all clients"""
        if self.primary_client:
            await self.primary_client.close()
        if self.fallback_client:
            await self.fallback_client.close()
    
    async def create(
        self,
        messages: Sequence[BaseChatMessage],
        cancellation_token: CancellationToken,
        **kwargs
    ) -> Any:
        """Create a chat completion with intelligent fallback"""
        
        # Check if we should try primary client again
        if self._should_reset_fallback():
            self._try_primary_client()
        
        # Try current client
        try:
            if not self.current_client:
                raise Exception("No client available")
            
            client_name = "Groq" if isinstance(self.current_client, GroqChatCompletionClient) else "Hugging Face"
            logging.info(f"🤖 Using {client_name} client for request")
            
            response = await self.current_client.create(messages, cancellation_token, **kwargs)
            
            # If we successfully used fallback, log it
            if self.fallback_active:
                logging.info("✅ Fallback client request successful")
            
            return response
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # Check if this is a rate limiting or API error that should trigger fallback
            should_fallback = any(phrase in error_msg for phrase in [
                'rate limit', '429', 'too many requests', 'quota exceeded',
                'api error', 'timeout', 'connection error'
            ])
            
            if should_fallback and not self.fallback_active and self.fallback_client:
                logging.warning(f"⚠️ Primary client failed: {e}")
                self._activate_fallback(str(e))
                
                # Retry with fallback client
                try:
                    logging.info("🔄 Retrying with fallback client...")
                    response = await self.current_client.create(messages, cancellation_token, **kwargs)
                    logging.info("✅ Fallback client request successful")
                    return response
                    
                except Exception as fallback_error:
                    logging.error(f"❌ Fallback client also failed: {fallback_error}")
                    # Return a helpful error response
                    class FallbackErrorResponse:
                        def __init__(self, primary_error: str, fallback_error: str):
                            self.content = (
                                f"❌ Sorry, I couldn't process your question. Both API services are currently unavailable.\n\n"
                                f"Primary service error: {primary_error}\n"
                                f"Fallback service error: {fallback_error}\n\n"
                                f"Please try again in a few minutes. If the problem persists, "
                                f"this might be due to high demand on the AI services."
                            )
                            self.choices = [self]
                            self.message = self
                        
                        def __str__(self):
                            return self.content
                    
                    return FallbackErrorResponse(str(e), str(fallback_error))
            
            else:
                # If fallback is already active or no fallback available, return error
                logging.error(f"❌ Client request failed: {e}")
                
                class ErrorResponse:
                    def __init__(self, error_msg: str):
                        self.content = (
                            f"❌ Sorry, I couldn't process your question. Please try rephrasing it.\n\n"
                            f"Technical details: {error_msg}"
                        )
                        self.choices = [self]
                        self.message = self
                    
                    def __str__(self):
                        return self.content
                
                return ErrorResponse(str(e))


def create_smart_fallback_client() -> SmartFallbackClient:
    """Create a smart fallback client"""
    return SmartFallbackClient()


def test_smart_fallback_client():
    """Test the smart fallback client"""
    try:
        client = create_smart_fallback_client()
        print("✅ Smart fallback client created successfully")
        
        # Test basic functionality
        import asyncio
        
        async def test_call():
            messages = [TextMessage(content="Show me total CHWs in Kenya", source="user")]
            response = await client.create(messages, CancellationToken())
            return response
        
        response = asyncio.run(test_call())
        print(f"✅ Test call successful: {response.content[:100]}...")
        return True
        
    except Exception as e:
        print(f"❌ Smart fallback client test failed: {e}")
        return False


if __name__ == "__main__":
    test_smart_fallback_client()
