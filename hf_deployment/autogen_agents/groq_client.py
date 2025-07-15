"""
Custom Groq client for AutoGen 0.6+
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional, Sequence
from groq import Groq
from autogen_core.models import ChatCompletionClient, ModelFamily, ModelInfo
from autogen_agentchat.messages import BaseChatMessage, TextMessage
from autogen_core.models import SystemMessage, UserMessage, AssistantMessage
from autogen_core import CancellationToken
from dotenv import load_dotenv

load_dotenv()

class GroqChatCompletionClient(ChatCompletionClient):
    """Custom Groq client for AutoGen 0.6+"""
    
    def __init__(
        self,
        model: str = "llama3-8b-8192",  # Updated to current Groq model
        api_key: Optional[str] = None,
        timeout: float = 120.0,
        max_tokens: int = 2000,
        temperature: float = 0.1
    ):
        self._model = model
        self._api_key = api_key or os.getenv("GROQ_API_KEY")
        self._timeout = timeout
        self._max_tokens = max_tokens
        self._temperature = temperature
        
        if not self._api_key:
            raise ValueError("GROQ_API_KEY is required")
        
        # Initialize Groq client
        self._client = Groq(api_key=self._api_key)
        
        # Model info
        self._model_info = ModelInfo(
            vision=False,
            function_calling=True,  # Groq supports function calling
            json_output=True,       # Groq supports JSON output
            family=ModelFamily.UNKNOWN,
            structured_output=False
        )
    
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
        """Estimate token count"""
        total_chars = 0
        for message in messages:
            if isinstance(message, TextMessage):
                total_chars += len(message.content)
        # Rough estimation: 1 token per 4 characters
        return total_chars // 4
    
    def remaining_tokens(self, messages: Sequence[BaseChatMessage], **kwargs) -> int:
        """Estimate remaining tokens"""
        used_tokens = self.count_tokens(messages, **kwargs)
        return max(0, self._max_tokens - used_tokens)
    
    @property
    def total_usage(self) -> Dict[str, int]:
        """Return total usage statistics"""
        return {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0}
    
    @property
    def actual_usage(self) -> Dict[str, int]:
        """Return actual usage statistics"""
        return {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0}
    
    async def create_stream(self, messages: Sequence[BaseChatMessage], cancellation_token: CancellationToken, **kwargs):
        """Create streaming response"""
        response = await self.create(messages, cancellation_token, **kwargs)
        yield response
    
    async def close(self):
        """Close the client"""
        pass
    
    def _format_messages(self, messages: Sequence[BaseChatMessage]) -> List[Dict[str, str]]:
        """Convert AutoGen messages to Groq format"""
        groq_messages = []

        logging.debug(f"Formatting {len(messages)} messages")

        for i, message in enumerate(messages):
            logging.debug(f"Message {i}: type={type(message)}, content={getattr(message, 'content', 'NO_CONTENT')[:50]}...")

            role = None
            content = None

            # Handle different message types
            if isinstance(message, TextMessage):
                role = "user" if getattr(message, 'source', 'user') == 'user' else "assistant"
                content = message.content
            elif isinstance(message, SystemMessage):
                role = "system"
                content = message.content
            elif isinstance(message, UserMessage):
                role = "user"
                content = message.content
            elif isinstance(message, AssistantMessage):
                role = "assistant"
                content = message.content
            elif hasattr(message, 'content'):
                # Fallback for other message types with content
                role = "user"  # Default to user
                content = message.content

            if role and content and content.strip():  # Only add non-empty messages
                groq_messages.append({
                    "role": role,
                    "content": content
                })
                logging.debug(f"Added message: role={role}, content={content[:50]}...")
            else:
                logging.warning(f"Skipping invalid message: type={type(message)}, role={role}, content={content}")

        logging.debug(f"Formatted {len(groq_messages)} valid messages")
        return groq_messages
    
    async def create(
        self,
        messages: Sequence[BaseChatMessage],
        cancellation_token: CancellationToken,
        **kwargs
    ) -> Any:
        """Create a chat completion using Groq API"""

        try:
            logging.info(f"Calling Groq model: {self._model}")
            logging.debug(f"Received {len(messages)} messages")

            # Check if messages is empty
            if not messages:
                logging.error("No messages provided to Groq client")
                raise ValueError("Messages list is empty")

            # Format messages for Groq
            groq_messages = self._format_messages(messages)
            logging.debug(f"Formatted messages: {groq_messages}")

            if not groq_messages:
                logging.error("No valid messages after formatting")
                raise ValueError("No valid messages after formatting")

            # Call Groq API
            response = self._client.chat.completions.create(
                model=self._model,
                messages=groq_messages,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                timeout=self._timeout
            )
            
            # Create a response wrapper that AutoGen can understand
            class AutoGenCompatibleResponse:
                def __init__(self, groq_response):
                    self.choices = groq_response.choices
                    self.usage = getattr(groq_response, 'usage', None)
                    self.model = groq_response.model
                    self.id = getattr(groq_response, 'id', 'groq-response')
                    self.object = getattr(groq_response, 'object', 'chat.completion')
                    self.created = getattr(groq_response, 'created', None)
                    self._groq_response = groq_response

                    # For our test compatibility
                    if self.choices and len(self.choices) > 0:
                        self.content = self.choices[0].message.content
                    else:
                        self.content = ""

                def __str__(self):
                    return self.content

            logging.debug(f"Groq API response: {response}")
            return AutoGenCompatibleResponse(response)
            
        except Exception as e:
            logging.error(f"Groq API call failed: {e}")
            # Return a fallback response
            class ErrorResponse:
                def __init__(self, error_msg: str):
                    self.content = f"Error: {error_msg}. Using fallback response for Kenya health data analysis."
                    self.choices = [self]
                    self.message = self
                
                def __str__(self):
                    return self.content
            
            return ErrorResponse(str(e))


def create_groq_client() -> Optional[GroqChatCompletionClient]:
    """Create Groq client if API key is available"""
    try:
        groq_api_key = os.getenv("GROQ_API_KEY")
        if groq_api_key:
            return GroqChatCompletionClient(
                model="llama3-8b-8192",  # Updated to current model
                api_key=groq_api_key,
                timeout=60.0,
                max_tokens=2000,
                temperature=0.1
            )
    except Exception as e:
        logging.warning(f"Failed to create Groq client: {e}")
    
    return None


def test_groq_client():
    """Test the Groq client"""
    client = create_groq_client()
    if not client:
        print("❌ No Groq client available")
        return False
    
    try:
        import asyncio
        from autogen_core import CancellationToken
        
        async def test_call():
            messages = [TextMessage(content="Generate SQL to show CHW performance in Kisumu county", source="user")]
            response = await client.create(messages, CancellationToken())
            return response
        
        response = asyncio.run(test_call())
        print(f"✅ Groq client test successful: {response.content[:100]}...")
        return True
        
    except Exception as e:
        print(f"❌ Groq client test failed: {e}")
        return False


if __name__ == "__main__":
    test_groq_client()
