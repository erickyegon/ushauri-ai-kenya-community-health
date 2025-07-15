#!/usr/bin/env python3
"""
Comprehensive Shock Test for Kenya Health AI System
Tests every component to identify performance bottlenecks and errors
"""

import asyncio
import time
import logging
import traceback
import sys
import os
from datetime import datetime
import pandas as pd

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('shock_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ShockTester:
    """Comprehensive system testing class"""
    
    def __init__(self):
        self.results = {}
        self.start_time = None
        self.db_connection = None
        
    def log_test_result(self, test_name, success, duration, error=None, details=None):
        """Log test results"""
        self.results[test_name] = {
            'success': success,
            'duration': duration,
            'error': str(error) if error else None,
            'details': details,
            'timestamp': datetime.now().isoformat()
        }
        
        status = "✅ PASS" if success else "❌ FAIL"
        logger.info(f"{status} {test_name} ({duration:.2f}s)")
        if error:
            logger.error(f"Error: {error}")
    
    async def test_database_connection(self):
        """Test database connectivity and performance"""
        logger.info("🔍 Testing Database Connection...")
        start_time = time.time()
        
        try:
            from tools.db import connect_db, test_connection, execute_sql_query
            
            # Test connection creation
            self.db_connection = connect_db()
            if not self.db_connection:
                raise Exception("Failed to create database connection")
            
            # Test basic query
            test_df = execute_sql_query(self.db_connection, "SELECT 1 as test")
            if test_df is None or test_df.empty:
                raise Exception("Basic query failed")

            # Test table existence
            tables_df = execute_sql_query(self.db_connection, """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
            """)
            
            duration = time.time() - start_time
            self.log_test_result(
                "Database Connection", 
                True, 
                duration,
                details=f"Found {len(tables_df)} tables"
            )
            return True
            
        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result("Database Connection", False, duration, e)
            return False
    
    async def test_groq_api(self):
        """Test Groq API connectivity and performance"""
        logger.info("🔍 Testing Groq API...")
        start_time = time.time()
        
        try:
            from autogen_agents.groq_client import create_groq_client
            
            client = create_groq_client()
            if not client:
                raise Exception("Failed to create Groq client")
            
            # Test simple API call with timeout
            test_response = await asyncio.wait_for(
                self._test_groq_call(client),
                timeout=10.0  # 10 second timeout
            )
            
            duration = time.time() - start_time
            self.log_test_result(
                "Groq API", 
                True, 
                duration,
                details=f"Response length: {len(str(test_response))}"
            )
            return True
            
        except asyncio.TimeoutError:
            duration = time.time() - start_time
            self.log_test_result("Groq API", False, duration, "API call timeout (>10s)")
            return False
        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result("Groq API", False, duration, e)
            return False
    
    async def _test_groq_call(self, client):
        """Helper method for Groq API test"""
        try:
            from autogen_agentchat.messages import TextMessage
            from autogen_core import CancellationToken

            # Use the custom client's create method
            message = TextMessage(content="Say 'test' in one word", source="user")
            cancellation_token = CancellationToken()

            response = await client.create([message], cancellation_token)

            if hasattr(response, 'content'):
                return response.content
            elif hasattr(response, 'choices') and response.choices:
                return response.choices[0].message.content
            else:
                return str(response)
        except Exception as e:
            raise Exception(f"Groq API call failed: {e}")
    
    async def test_agent_creation(self):
        """Test agent creation and initialization"""
        logger.info("🔍 Testing Agent Creation...")
        start_time = time.time()
        
        try:
            from autogen_agents.group_chat import (
                create_sql_generator_agent,
                create_analysis_agent,
                create_visualization_agent
            )
            
            # Test each agent creation
            agents = {}
            agent_types = [
                ("SQL Generator", create_sql_generator_agent),
                ("Analysis", create_analysis_agent),
                ("Visualization", create_visualization_agent)
            ]
            
            for name, creator_func in agent_types:
                agent_start = time.time()
                agent = creator_func()
                agent_duration = time.time() - agent_start
                
                if agent is None:
                    raise Exception(f"{name} agent creation returned None")
                
                agents[name] = {
                    'agent': agent,
                    'creation_time': agent_duration
                }
                logger.info(f"  ✅ {name} agent created in {agent_duration:.2f}s")
            
            duration = time.time() - start_time
            self.log_test_result(
                "Agent Creation", 
                True, 
                duration,
                details=f"Created {len(agents)} agents"
            )
            return agents
            
        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result("Agent Creation", False, duration, e)
            return None
    
    async def test_sql_generation(self, agents):
        """Test SQL generation performance"""
        logger.info("🔍 Testing SQL Generation...")
        start_time = time.time()
        
        try:
            if not agents or "SQL Generator" not in agents:
                raise Exception("SQL Generator agent not available")
            
            from autogen_agents.group_chat import call_agent_sync
            
            sql_agent = agents["SQL Generator"]["agent"]
            test_query = "Show me all CHWs from Kisumu county"
            
            # Test with timeout
            response = await asyncio.wait_for(
                asyncio.to_thread(call_agent_sync, sql_agent, test_query),
                timeout=30.0  # 30 second timeout
            )
            
            if response is None:
                raise Exception("SQL agent returned None")
            
            # Extract SQL content with enhanced debugging
            sql_content = None
            logger.info(f"Response type: {type(response)}")
            logger.info(f"Response: {str(response)[:500]}...")

            # Handle AutoGen Response objects
            if hasattr(response, 'chat_message'):
                # AutoGen Response object
                chat_message = response.chat_message
                if hasattr(chat_message, 'content'):
                    sql_content = chat_message.content
                    logger.info(f"Found content in chat_message: {str(sql_content)[:200]}...")
                else:
                    sql_content = str(chat_message)
                    logger.info(f"Converting chat_message to string: {sql_content[:200]}...")
            elif hasattr(response, 'content'):
                sql_content = response.content
                logger.info(f"Found content attribute: {str(sql_content)[:200]}...")
            elif isinstance(response, str):
                sql_content = response
                logger.info(f"Response is string: {sql_content[:200]}...")
            elif isinstance(response, list) and len(response) > 0:
                # Handle list responses (common with AutoGen)
                last_response = response[-1]
                logger.info(f"Response is list, last item type: {type(last_response)}")
                if hasattr(last_response, 'chat_message'):
                    chat_message = last_response.chat_message
                    if hasattr(chat_message, 'content'):
                        sql_content = chat_message.content
                        logger.info(f"Found content in list chat_message: {str(sql_content)[:200]}...")
                elif hasattr(last_response, 'content'):
                    sql_content = last_response.content
                    logger.info(f"Found content in list item: {str(sql_content)[:200]}...")
                else:
                    sql_content = str(last_response)
                    logger.info(f"Converting list item to string: {sql_content[:200]}...")
            else:
                # Try to convert to string as fallback
                sql_content = str(response)
                logger.info(f"Converting response to string: {sql_content[:200]}...")

            # Clean SQL content if found
            if sql_content:
                # Remove markdown formatting if present
                if sql_content.startswith("```sql"):
                    sql_content = sql_content.replace("```sql", "").replace("```", "").strip()
                elif sql_content.startswith("```"):
                    sql_content = sql_content.replace("```", "").strip()

                logger.info(f"Cleaned SQL content: {sql_content[:200]}...")

            if not sql_content or sql_content.strip() == "" or sql_content == "None":
                raise Exception(f"No SQL content in response. Response type: {type(response)}, Content: {str(response)[:200]}")
            
            duration = time.time() - start_time
            self.log_test_result(
                "SQL Generation", 
                True, 
                duration,
                details=f"Generated SQL: {len(sql_content)} chars"
            )
            return sql_content
            
        except asyncio.TimeoutError:
            duration = time.time() - start_time
            self.log_test_result("SQL Generation", False, duration, "SQL generation timeout (>30s)")
            return None
        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result("SQL Generation", False, duration, e)
            return None
    
    async def test_query_execution(self, sql_content):
        """Test SQL query execution"""
        logger.info("🔍 Testing Query Execution...")
        start_time = time.time()
        
        try:
            if not sql_content or not self.db_connection:
                raise Exception("No SQL content or database connection")
            
            from tools.db import execute_sql_query
            
            # Clean SQL content
            sql_query = sql_content.strip()
            if sql_query.startswith("```sql"):
                sql_query = sql_query.replace("```sql", "").replace("```", "").strip()
            
            # Execute with timeout
            df = await asyncio.wait_for(
                asyncio.to_thread(execute_sql_query, self.db_connection, sql_query),
                timeout=15.0  # 15 second timeout
            )
            
            if df is None:
                raise Exception("Query execution returned None")
            
            if 'error' in df.columns:
                raise Exception(f"SQL Error: {df['error'].iloc[0] if not df.empty else 'Unknown error'}")
            
            duration = time.time() - start_time
            self.log_test_result(
                "Query Execution", 
                True, 
                duration,
                details=f"Returned {len(df)} rows"
            )
            return df
            
        except asyncio.TimeoutError:
            duration = time.time() - start_time
            self.log_test_result("Query Execution", False, duration, "Query execution timeout (>15s)")
            return None
        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result("Query Execution", False, duration, e)
            return None
    
    async def test_full_workflow(self):
        """Test complete end-to-end workflow"""
        logger.info("🔍 Testing Full Workflow...")
        start_time = time.time()
        
        try:
            from autogen_agents.group_chat import run_group_chat
            
            if not self.db_connection:
                raise Exception("No database connection available")
            
            test_question = "Show me CHW performance in Kisumu county"
            
            # Test with timeout
            result = await asyncio.wait_for(
                asyncio.to_thread(run_group_chat, test_question, self.db_connection),
                timeout=60.0  # 60 second timeout for full workflow
            )
            
            if not result:
                raise Exception("Workflow returned no result")
            
            if 'error' in result:
                raise Exception(f"Workflow error: {result['error']}")
            
            duration = time.time() - start_time
            self.log_test_result(
                "Full Workflow", 
                True, 
                duration,
                details=f"Result keys: {list(result.keys())}"
            )
            return result
            
        except asyncio.TimeoutError:
            duration = time.time() - start_time
            self.log_test_result("Full Workflow", False, duration, "Full workflow timeout (>60s)")
            return None
        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result("Full Workflow", False, duration, e)
            return None
    
    async def run_all_tests(self):
        """Run all shock tests"""
        logger.info("🚀 Starting Comprehensive Shock Test...")
        self.start_time = time.time()
        
        # Test sequence
        tests = [
            self.test_database_connection(),
            self.test_groq_api(),
        ]
        
        # Run basic tests first
        for test in tests:
            await test
        
        # Test agents if basic tests pass
        agents = await self.test_agent_creation()
        
        if agents:
            sql_content = await self.test_sql_generation(agents)
            
            if sql_content:
                df = await self.test_query_execution(sql_content)
        
        # Test full workflow
        await self.test_full_workflow()
        
        # Generate report
        self.generate_report()
    
    def generate_report(self):
        """Generate comprehensive test report"""
        total_duration = time.time() - self.start_time
        
        logger.info("\n" + "="*60)
        logger.info("📊 SHOCK TEST REPORT")
        logger.info("="*60)
        
        passed = sum(1 for r in self.results.values() if r['success'])
        total = len(self.results)
        
        logger.info(f"Total Tests: {total}")
        logger.info(f"Passed: {passed}")
        logger.info(f"Failed: {total - passed}")
        logger.info(f"Success Rate: {(passed/total)*100:.1f}%")
        logger.info(f"Total Duration: {total_duration:.2f}s")
        
        logger.info("\nDetailed Results:")
        for test_name, result in self.results.items():
            status = "✅" if result['success'] else "❌"
            logger.info(f"{status} {test_name}: {result['duration']:.2f}s")
            if result['error']:
                logger.info(f"   Error: {result['error']}")
            if result['details']:
                logger.info(f"   Details: {result['details']}")
        
        # Identify performance issues
        slow_tests = [name for name, result in self.results.items() 
                     if result['duration'] > 10.0]
        
        if slow_tests:
            logger.warning(f"\n⚠️  SLOW TESTS (>10s): {', '.join(slow_tests)}")
        
        # Save results to file
        import json
        with open('shock_test_results.json', 'w') as f:
            json.dump(self.results, f, indent=2)
        
        logger.info(f"\nResults saved to: shock_test_results.json")

async def main():
    """Main test runner"""
    tester = ShockTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())
