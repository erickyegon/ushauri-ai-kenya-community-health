#!/usr/bin/env python3
"""
Test Groq integration with AutoGen agents
"""

import asyncio
import logging
from autogen_agents.groq_client import create_groq_client
from autogen_agents.group_chat import create_sql_generator_agent, call_agent_sync
from autogen_agentchat.messages import TextMessage

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_groq_client():
    """Test basic Groq client functionality"""
    logger.info("Testing Groq client creation...")
    
    try:
        client = create_groq_client()
        if client:
            logger.info("✅ Groq client created successfully")
            return True
        else:
            logger.error("❌ Failed to create Groq client")
            return False
    except Exception as e:
        logger.error(f"❌ Error creating Groq client: {e}")
        return False

async def test_sql_agent():
    """Test SQL generator agent with Groq"""
    logger.info("Testing SQL generator agent...")
    
    try:
        agent = create_sql_generator_agent()
        if agent:
            logger.info("✅ SQL generator agent created successfully")
            
            # Test with a simple query
            test_message = TextMessage(
                content="Show me all CHWs from Kisumu county",
                source="user"
            )
            
            logger.info("Testing agent response...")
            response = await call_agent_sync(agent, test_message)
            
            if response:
                logger.info(f"✅ Agent responded: {response.content[:100]}...")
                return True
            else:
                logger.error("❌ Agent did not respond")
                return False
        else:
            logger.error("❌ Failed to create SQL generator agent")
            return False
    except Exception as e:
        logger.error(f"❌ Error testing SQL agent: {e}")
        return False

async def main():
    """Run all tests"""
    logger.info("🚀 Starting Groq integration tests...")
    
    # Test 1: Basic client
    client_test = await test_groq_client()
    
    # Test 2: SQL agent
    agent_test = await test_sql_agent()
    
    # Summary
    logger.info("\n" + "="*50)
    logger.info("TEST SUMMARY:")
    logger.info(f"Groq Client: {'✅ PASS' if client_test else '❌ FAIL'}")
    logger.info(f"SQL Agent: {'✅ PASS' if agent_test else '❌ FAIL'}")
    
    if client_test and agent_test:
        logger.info("🎉 All tests passed!")
        return True
    else:
        logger.info("⚠️ Some tests failed")
        return False

if __name__ == "__main__":
    asyncio.run(main())
