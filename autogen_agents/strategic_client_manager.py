"""
Strategic Client Manager for AutoGen 0.6+
Uses different APIs strategically based on operation type:
- Hugging Face: System initialization, table operations, stable operations
- Groq: Interactive queries, report generation, fast responses
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
from .emergency_fallback import create_emergency_fallback_client

load_dotenv()

class StrategicClientManager:
    """
    Strategic client manager that uses different APIs for different purposes:
    - HuggingFace: System operations, initialization, stable workflows
    - Groq: Interactive queries, fast responses, report generation
    """
    
    def __init__(self):
        self.hf_client = None
        self.groq_client = None
        self.emergency_client = None
        self.operation_stats = {
            'hf_calls': 0,
            'groq_calls': 0,
            'emergency_calls': 0,
            'hf_errors': 0,
            'groq_errors': 0,
            'emergency_errors': 0
        }
        
        # Initialize clients
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize both clients"""
        try:
            # Initialize Hugging Face (stable operations)
            self.hf_client = create_hf_client()
            if self.hf_client:
                logging.info("✅ Hugging Face client initialized (System Operations)")
            else:
                logging.warning("⚠️ Hugging Face client not available")
            
            # Initialize Groq (fast operations)
            self.groq_client = create_groq_client()
            if self.groq_client:
                logging.info("✅ Groq client initialized (Interactive Queries)")
            else:
                logging.warning("⚠️ Groq client not available")

            # Initialize Emergency Fallback (when all else fails)
            self.emergency_client = create_emergency_fallback_client()
            if self.emergency_client:
                logging.info("🚨 Emergency fallback system initialized (Last Resort)")

            if not self.hf_client and not self.groq_client and not self.emergency_client:
                raise ValueError("No API clients available. Please check your API keys.")
                
        except Exception as e:
            logging.error(f"Failed to initialize clients: {e}")
            raise
    
    def get_client_for_operation(self, operation_type: str) -> ChatCompletionClient:
        """
        Get the appropriate client based on operation type
        
        Args:
            operation_type: Type of operation
                - 'system': System initialization, table operations
                - 'query': Interactive queries, chatbot responses
                - 'report': Report generation, analysis
                - 'fallback': When primary client fails
        """
        
        if operation_type in ['system', 'initialization', 'table', 'schema']:
            # Use Hugging Face for stable system operations
            if self.hf_client:
                logging.info(f"🏗️ Using Hugging Face for {operation_type} operation")
                return self.hf_client
            elif self.groq_client:
                logging.info(f"🔄 Fallback to Groq for {operation_type} operation")
                return self.groq_client
            else:
                raise Exception("No clients available for system operations")
        
        elif operation_type in ['query', 'chat', 'interactive']:
            # Use Groq for fast interactive operations
            if self.groq_client:
                logging.info(f"⚡ Using Groq for {operation_type} operation")
                return self.groq_client
            elif self.hf_client:
                logging.info(f"🔄 Fallback to Hugging Face for {operation_type} operation")
                return self.hf_client
            else:
                raise Exception("No clients available for interactive operations")
        
        elif operation_type in ['report', 'analysis', 'visualization']:
            # Use Groq for report generation (faster)
            if self.groq_client:
                logging.info(f"📊 Using Groq for {operation_type} operation")
                return self.groq_client
            elif self.hf_client:
                logging.info(f"🔄 Fallback to Hugging Face for {operation_type} operation")
                return self.hf_client
            else:
                raise Exception("No clients available for report operations")
        
        else:
            # Default to most stable client
            if self.hf_client:
                logging.info(f"🔄 Using Hugging Face for unknown operation: {operation_type}")
                return self.hf_client
            elif self.groq_client:
                logging.info(f"🔄 Using Groq for unknown operation: {operation_type}")
                return self.groq_client
            else:
                raise Exception("No clients available")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics"""
        return {
            'operation_stats': self.operation_stats,
            'clients_available': {
                'hugging_face': self.hf_client is not None,
                'groq': self.groq_client is not None,
                'emergency_fallback': self.emergency_client is not None
            },
            'reliability_score': self._calculate_reliability_score()
        }

    def _calculate_reliability_score(self) -> float:
        """Calculate system reliability score based on success rates"""
        total_calls = sum([
            self.operation_stats['hf_calls'],
            self.operation_stats['groq_calls'],
            self.operation_stats['emergency_calls']
        ])

        total_errors = sum([
            self.operation_stats['hf_errors'],
            self.operation_stats['groq_errors'],
            self.operation_stats['emergency_errors']
        ])

        if total_calls == 0:
            return 1.0  # No calls yet, assume perfect

        success_rate = (total_calls - total_errors) / total_calls

        # Penalize emergency calls as they indicate API failures
        emergency_penalty = self.operation_stats['emergency_calls'] * 0.1

        return max(0.0, min(1.0, success_rate - emergency_penalty))


class StrategicChatCompletionClient(ChatCompletionClient):
    """
    Strategic wrapper that implements ChatCompletionClient interface
    while using different underlying clients based on operation context
    """
    
    def __init__(self, operation_type: str = 'system'):
        self.manager = StrategicClientManager()
        self.operation_type = operation_type
        self.current_client = self.manager.get_client_for_operation(operation_type)
        
        # Model info (combined capabilities)
        self._model_info = ModelInfo(
            vision=False,
            function_calling=True,  # Groq supports this
            json_output=True,       # Groq supports this
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
        """Create streaming response"""
        response = await self.create(messages, cancellation_token, **kwargs)
        yield response
    
    async def close(self):
        """Close the client"""
        if self.current_client:
            await self.current_client.close()
    
    async def create(
        self,
        messages: Sequence[BaseChatMessage],
        cancellation_token: CancellationToken,
        **kwargs
    ) -> Any:
        """Create a chat completion using the strategic client"""
        
        try:
            if not self.current_client:
                raise Exception("No client available")
            
            client_name = "Groq" if isinstance(self.current_client, GroqChatCompletionClient) else "Hugging Face"
            logging.info(f"🤖 Using {client_name} for {self.operation_type} operation")
            
            response = await self.current_client.create(messages, cancellation_token, **kwargs)
            
            # Update stats
            if isinstance(self.current_client, GroqChatCompletionClient):
                self.manager.operation_stats['groq_calls'] += 1
            else:
                self.manager.operation_stats['hf_calls'] += 1
            
            return response
            
        except Exception as e:
            # Update error stats
            if isinstance(self.current_client, GroqChatCompletionClient):
                self.manager.operation_stats['groq_errors'] += 1
            else:
                self.manager.operation_stats['hf_errors'] += 1
            
            # Check error type for better handling
            error_str = str(e).lower()
            is_server_error = any(phrase in error_str for phrase in [
                '500', 'server error', 'internal server error', 'service unavailable',
                'bad gateway', 'gateway timeout', 'internal error'
            ])
            is_rate_limit = any(phrase in error_str for phrase in [
                '429', 'rate limit', 'too many requests', 'quota exceeded'
            ])
            is_model_error = any(phrase in error_str for phrase in [
                'no model result', 'assertion', 'model result was produced'
            ])

            logging.error(f"❌ {client_name} client failed for {self.operation_type}: {e}")

            # Try fallback for recoverable errors
            if is_server_error or is_rate_limit or is_model_error:
                try:
                    # Get the opposite client for fallback
                    if isinstance(self.current_client, GroqChatCompletionClient):
                        fallback_client = self.manager.hf_client
                        fallback_name = "Hugging Face"
                    else:
                        fallback_client = self.manager.groq_client
                        fallback_name = "Groq"

                    if fallback_client and fallback_client != self.current_client:
                        logging.info(f"🔄 Switching to {fallback_name} fallback for {self.operation_type}")
                        response = await fallback_client.create(messages, cancellation_token, **kwargs)
                        logging.info(f"✅ Fallback to {fallback_name} successful")
                        return response
                except Exception as fallback_error:
                    logging.error(f"❌ Fallback to {fallback_name} also failed: {fallback_error}")

            # Last resort: Emergency fallback system
            if self.manager.emergency_client:
                try:
                    logging.warning("🚨 Activating emergency fallback system - both APIs failed")
                    response = await self.manager.emergency_client.create(messages, cancellation_token, **kwargs)
                    self.manager.operation_stats['emergency_calls'] += 1
                    logging.info("✅ Emergency fallback response generated")
                    return response
                except Exception as emergency_error:
                    logging.error(f"❌ Emergency fallback also failed: {emergency_error}")
                    self.manager.operation_stats['emergency_errors'] += 1

            # Final error response if everything fails
            class FinalErrorResponse:
                def __init__(self, error_msg: str, operation: str):
                    self.content = (
                        f"🚨 SYSTEM UNAVAILABLE 🚨\n\n"
                        f"All AI services are currently experiencing issues:\n"
                        f"- Primary API: Failed\n"
                        f"- Fallback API: Failed\n"
                        f"- Emergency System: Failed\n\n"
                        f"Operation: {operation}\n"
                        f"Error: {error_msg}\n\n"
                        f"Please contact your system administrator or try again later."
                    )
                    self.choices = [self]
                    self.message = self

                def __str__(self):
                    return self.content

            return FinalErrorResponse(str(e), self.operation_type)


def create_strategic_client(operation_type: str = 'system') -> StrategicChatCompletionClient:
    """
    Create a strategic client for specific operation type
    
    Args:
        operation_type: 'system', 'query', 'report', etc.
    """
    return StrategicChatCompletionClient(operation_type)


def test_strategic_client():
    """Test the strategic client system"""
    try:
        # Test system operations client
        system_client = create_strategic_client('system')
        print("✅ System operations client created")
        
        # Test query client
        query_client = create_strategic_client('query')
        print("✅ Query client created")
        
        # Test report client
        report_client = create_strategic_client('report')
        print("✅ Report client created")
        
        return True
        
    except Exception as e:
        print(f"❌ Strategic client test failed: {e}")
        return False


if __name__ == "__main__":
    test_strategic_client()
