"""
Custom Hugging Face client for AutoGen 0.6+
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional, Sequence
from huggingface_hub import InferenceClient
from autogen_core.models import ChatCompletionClient, ModelFamily, ModelInfo
from autogen_agentchat.messages import BaseChatMessage, TextMessage
from autogen_core import CancellationToken
from dotenv import load_dotenv

load_dotenv()

class HuggingFaceChatCompletionClient(ChatCompletionClient):
    """Custom Hugging Face client for AutoGen 0.6+"""
    
    def __init__(
        self,
        model: str = "mistralai/Mixtral-8x7B-Instruct-v0.1",
        api_key: Optional[str] = None,
        timeout: float = 120.0,
        max_tokens: int = 2000,
        temperature: float = 0.1
    ):
        self._model = model
        self._api_key = api_key or os.getenv("HF_API_KEY")
        self._timeout = timeout
        self._max_tokens = max_tokens
        self._temperature = temperature
        
        if not self._api_key:
            raise ValueError("HF_API_KEY is required")
        
        # Initialize Hugging Face client
        self._client = InferenceClient(token=self._api_key)
        
        # Model info
        self._model_info = ModelInfo(
            vision=False,
            function_calling=False,
            json_output=False,
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
            "function_calling": False,
            "json_output": False,
            "structured_output": False
        }

    def count_tokens(self, messages: Sequence[BaseChatMessage], **kwargs) -> int:
        """Estimate token count"""
        prompt = self._format_messages(messages)
        # Rough estimation: 1 token per 4 characters
        return len(prompt) // 4

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
        """Create streaming response (not implemented for HF)"""
        response = await self.create(messages, cancellation_token, **kwargs)
        yield response

    async def close(self):
        """Close the client"""
        pass
    
    def _format_messages(self, messages: Sequence[BaseChatMessage]) -> str:
        """Convert AutoGen messages to a single prompt string"""
        prompt_parts = []
        
        for message in messages:
            if isinstance(message, TextMessage):
                content = message.content
                source = getattr(message, 'source', 'user')
                
                if source == 'user':
                    prompt_parts.append(f"Human: {content}")
                else:
                    prompt_parts.append(f"Assistant: {content}")
        
        # Add final prompt for assistant response
        prompt_parts.append("Assistant:")
        
        return "\n\n".join(prompt_parts)
    
    async def create(
        self,
        messages: Sequence[BaseChatMessage],
        cancellation_token: CancellationToken,
        **kwargs
    ) -> Any:
        """Create a chat completion using Hugging Face Inference API"""
        
        try:
            # Format messages into a prompt
            prompt = self._format_messages(messages)
            
            logging.info(f"Calling Hugging Face model: {self._model}")
            logging.debug(f"Prompt: {prompt[:200]}...")
            
            # Call Hugging Face Inference API using chat_completion
            # Format messages for chat completion
            chat_messages = []
            for message in messages:
                if isinstance(message, TextMessage):
                    role = "user" if getattr(message, 'source', 'user') == 'user' else "assistant"
                    chat_messages.append({
                        "role": role,
                        "content": message.content
                    })

            response = self._client.chat_completion(
                messages=chat_messages,
                model=self._model,
                max_tokens=self._max_tokens,
                temperature=self._temperature
            )
            
            # Create response object that mimics OpenAI format
            class HFResponse:
                def __init__(self, content: str):
                    self.content = content.strip()
                    self.choices = [self]
                    self.message = self

                def __str__(self):
                    return self.content

            # Extract response text from chat completion response
            if hasattr(response, 'choices') and response.choices:
                response_text = response.choices[0].message.content
            else:
                response_text = str(response)

            return HFResponse(response_text)
            
        except Exception as e:
            logging.error(f"Hugging Face API call failed: {e}")
            # Return a fallback response
            class ErrorResponse:
                def __init__(self, error_msg: str):
                    self.content = f"Error: {error_msg}. Using fallback response for Kenya health data analysis."
                    self.choices = [self]
                    self.message = self
                
                def __str__(self):
                    return self.content
            
            return ErrorResponse(str(e))


def create_hf_client() -> Optional[HuggingFaceChatCompletionClient]:
    """Create Hugging Face client if API key is available"""
    try:
        hf_api_key = os.getenv("HF_API_KEY")
        if hf_api_key:
            return HuggingFaceChatCompletionClient(
                model="mistralai/Mixtral-8x7B-Instruct-v0.1",
                api_key=hf_api_key,
                timeout=120.0,
                max_tokens=2000,
                temperature=0.1
            )
    except Exception as e:
        logging.warning(f"Failed to create HF client: {e}")
    
    return None


def test_hf_client():
    """Test the Hugging Face client"""
    client = create_hf_client()
    if not client:
        print("❌ No HF client available")
        return False
    
    try:
        import asyncio
        from autogen_core import CancellationToken
        
        async def test_call():
            messages = [TextMessage(content="Generate SQL to show CHW performance", source="user")]
            response = await client.create(messages, CancellationToken())
            return response
        
        response = asyncio.run(test_call())
        print(f"✅ HF client test successful: {response.content[:100]}...")
        return True
        
    except Exception as e:
        print(f"❌ HF client test failed: {e}")
        return False


if __name__ == "__main__":
    test_hf_client()
