"""
autogen_agents/group_chat.py - Core AutoGen v0.6+ Multi-Agent System
"""

import os
import pandas as pd
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.messages import TextMessage
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core.models import ModelFamily, ModelInfo
from autogen_core import CancellationToken
from .hf_client import create_hf_client
from .groq_client import create_groq_client
from .smart_fallback_client import create_smart_fallback_client
from .strategic_client_manager import create_strategic_client
from tools.db import execute_sql_query
import plotly.express as px
import plotly.graph_objects as go
import json
from typing import Dict, Any, List, Optional
import logging
import asyncio
from dotenv import load_dotenv
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import functools

# Import performance monitoring
try:
    from monitoring.performance_monitor import record_performance_metric
except ImportError:
    # Fallback if monitoring module not available
    def record_performance_metric(metric_name: str, value: float, unit: str = 'seconds', metadata=None):
        pass

# Import enhanced caching
try:
    from caching.enhanced_cache import (
        get_cached_api_response, cache_api_response,
        get_cached_sql_query, cache_sql_query,
        get_cached_agent_response, cache_agent_response,
        get_cache_statistics
    )
except ImportError:
    # Fallback if caching module not available
    def get_cached_api_response(endpoint: str, params: dict): return None
    def cache_api_response(endpoint: str, params: dict, response, ttl_seconds: int = 3600): pass
    def get_cached_sql_query(query: str): return None
    def cache_sql_query(query: str, result, ttl_seconds: int = 1800): pass
    def get_cached_agent_response(agent_type: str, prompt: str): return None
    def cache_agent_response(agent_type: str, prompt: str, response, ttl_seconds: int = 900): pass
    def get_cache_statistics(): return {}

# Load environment variables
load_dotenv()

# Global model client for reuse
_model_client = None

# Agent cache for performance optimization
_agent_cache = {
    'sql_generator': None,
    'analyzer': None,
    'visualizer': None,
    'cache_timestamp': None
}

# Cache timeout in seconds (5 minutes)
AGENT_CACHE_TIMEOUT = 300

# Performance monitoring
_performance_metrics = {
    'sql_generation_times': [],
    'analysis_times': [],
    'visualization_times': [],
    'total_workflow_times': []
}


def get_model_client(operation_type: str = 'system'):
    """
    Configure model client for AutoGen 0.6+ with strategic API selection

    Args:
        operation_type: 'system', 'query', 'report', etc.
    """

    # Priority 1: Strategic Client Manager (HF for system, Groq for queries)
    try:
        groq_api_key = os.getenv("GROQ_API_KEY")
        hf_api_key = os.getenv("HF_API_KEY")

        if groq_api_key or hf_api_key:
            logging.info(f"🎯 Using Strategic Client for {operation_type} operations")
            return create_strategic_client(operation_type)
    except Exception as e:
        logging.warning(f"Failed to initialize Strategic client: {e}")

    # Priority 2: Smart Fallback Client (Groq -> Hugging Face)
    try:
        if groq_api_key or hf_api_key:
            logging.info("🔄 Using Smart Fallback Client (HF -> Groq)")
            return create_smart_fallback_client()
    except Exception as e:
        logging.warning(f"Failed to initialize Smart Fallback client: {e}")

    # Priority 3: Custom Hugging Face Client (Most Stable)
    hf_client = create_hf_client()
    if hf_client:
        logging.info("✅ Using custom Hugging Face client")
        return hf_client

    # Priority 4: Groq via OpenAI-compatible API (Fallback)
    groq_api_key = os.getenv("GROQ_API_KEY")
    if groq_api_key:
        try:
            logging.info("🔄 Using Groq via OpenAI-compatible API (fallback)")
            return OpenAIChatCompletionClient(
                model="llama-3.1-8b-instant",
                api_key=groq_api_key,
                base_url="https://api.groq.com/openai/v1",
                model_info=ModelInfo(
                    vision=False,
                    function_calling=True,
                    json_output=True,
                    family=ModelFamily.UNKNOWN,
                    structured_output=False
                ),
                timeout=60.0,
                max_retries=3,
                temperature=0.1,
                max_tokens=2000
            )
        except Exception as e:
            logging.warning(f"Failed to initialize Groq OpenAI client: {e}")

    # Priority 5: OpenAI API (fallback)
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if openai_api_key:
        try:
            return OpenAIChatCompletionClient(
                model="gpt-3.5-turbo",
                api_key=openai_api_key,
                temperature=0.1,
                max_tokens=2000
            )
        except Exception as e:
            logging.warning(f"Failed to initialize OpenAI client: {e}")

    # Priority 6: Local Ollama (if available)
    try:
        import requests
        # Test if Ollama is running locally
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            return OpenAIChatCompletionClient(
                model="llama3.2:3b",  # or any available model
                api_key="placeholder",
                base_url="http://localhost:11434/v1",
                model_info=ModelInfo(
                    vision=False,
                    function_calling=False,
                    json_output=False,
                    family=ModelFamily.UNKNOWN,
                    structured_output=False
                ),
                timeout=60.0,
                temperature=0.1,
                max_tokens=2000
            )
    except Exception:
        pass  # Ollama not available

    # No model client available
    logging.warning("No model client available. Please set HF_API_KEY or GROQ_API_KEY environment variable.")
    return None


def is_cache_valid():
    """Check if agent cache is still valid"""
    if _agent_cache['cache_timestamp'] is None:
        return False
    return time.time() - _agent_cache['cache_timestamp'] < AGENT_CACHE_TIMEOUT


def get_cached_agents():
    """Get cached agents if valid, otherwise create new ones"""
    if is_cache_valid() and all(_agent_cache[key] is not None for key in ['sql_generator', 'analyzer', 'visualizer']):
        logging.info("Using cached agents for performance")
        return _agent_cache['sql_generator'], _agent_cache['analyzer'], _agent_cache['visualizer']

    # Create new agents and cache them
    logging.info("Creating new agents and caching them")
    sql_gen = create_sql_generator_agent()
    analyzer = create_analysis_agent()
    viz_agent = create_visualization_agent()

    # Cache the agents
    _agent_cache['sql_generator'] = sql_gen
    _agent_cache['analyzer'] = analyzer
    _agent_cache['visualizer'] = viz_agent
    _agent_cache['cache_timestamp'] = time.time()

    return sql_gen, analyzer, viz_agent


async def call_agent_async(agent, message_content: str):
    """Async wrapper for agent calls with improved error handling"""
    try:
        logging.debug(f"Starting agent call with message: {message_content[:100]}...")

        cancellation_token = CancellationToken()
        message = TextMessage(content=message_content, source="user")
        messages = [message]

        logging.debug(f"Created {len(messages)} messages")
        logging.debug(f"Calling agent.on_messages...")

        # Add timeout to prevent hanging
        response = await asyncio.wait_for(
            agent.on_messages(messages, cancellation_token),
            timeout=30.0  # 30 second timeout
        )

        logging.debug(f"Agent response received: type={type(response)}")

        if response is None:
            logging.error("Agent returned None response")
            return None

        # Handle different response types
        if hasattr(response, 'content'):
            logging.debug(f"Agent response content: {str(response.content)[:200]}...")
            return response
        elif isinstance(response, list) and len(response) > 0:
            # Handle list responses (common with AutoGen)
            last_response = response[-1]
            if hasattr(last_response, 'content'):
                logging.debug(f"Agent response content: {str(last_response.content)[:200]}...")
                return last_response
            else:
                logging.debug(f"Agent response (list): {str(response)[:200]}...")
                return response
        else:
            logging.debug(f"Agent response (other): {str(response)[:200]}...")
            return response

    except asyncio.TimeoutError:
        logging.error("Agent call timed out after 30 seconds")
        return None
    except Exception as e:
        logging.error(f"Agent call failed with exception: {e}")
        import traceback
        logging.error(f"Traceback: {traceback.format_exc()}")
        return None


def call_agent_sync(agent, message_content: str, cache_key_prefix: str = None):
    """Synchronous wrapper for agent calls with improved cleanup and caching"""
    try:
        # Check cache first if cache key prefix provided
        if cache_key_prefix:
            cached_response = get_cached_agent_response(cache_key_prefix, message_content)
            if cached_response:
                logging.info(f"Using cached response for {cache_key_prefix}")
                return cached_response

        # Check if there's already an event loop running
        try:
            loop = asyncio.get_running_loop()
            # If we're in an async context, create a task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(_run_agent_in_new_loop, agent, message_content)
                response = future.result(timeout=35)  # 35 second timeout

                # Cache the response if cache key prefix provided
                if cache_key_prefix and response:
                    cache_agent_response(cache_key_prefix, message_content, response)
                    logging.info(f"Cached response for {cache_key_prefix}")

                return response
        except RuntimeError:
            # No running loop, create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                response = loop.run_until_complete(call_agent_async(agent, message_content))

                # Cache the response if cache key prefix provided
                if cache_key_prefix and response:
                    cache_agent_response(cache_key_prefix, message_content, response)
                    logging.info(f"Cached response for {cache_key_prefix}")

                return response
            finally:
                # Properly cleanup pending tasks
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.close()
    except Exception as e:
        logging.error(f"Sync agent call failed: {e}")
        return None

def _run_agent_in_new_loop(agent, message_content: str):
    """Helper function to run agent in a new event loop"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        response = loop.run_until_complete(call_agent_async(agent, message_content))
        return response
    finally:
        # Cleanup pending tasks
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()


def create_sql_generator_agent():
    """Create SQL generator agent using AutoGen 0.6+ with strategic client"""
    model_client = get_model_client('system')  # Use stable HF for SQL generation
    if not model_client:
        return None

    system_message = """You are an expert SQL generator specializing in Kenya health data analysis for Kisumu, Busia, and Vihiga counties with data from December 2024 to June 2025.

DATABASE SCHEMA (Kenya Health System):

CORE TABLES:
1. supervision/supervision_visits - CHW supervision assessments
   - chv_uuid, chv_name: CHW identifiers and names
   - county: Kisumu, Busia, Vihiga (main focus counties)
   - reported: Date of supervision (2024-12-01 to 2025-06-30)
   - calc_assessment_score: Overall supervision score (0-100)
   - calc_pneumonia_score: Pneumonia management score (0-100)
   - calc_malaria_score: Malaria treatment score (0-100)
   - calc_family_planning_score: Family planning service score (0-100)
   - calc_immunization_score: Immunization delivery score (0-100)
   - calc_nutrition_score: Nutrition counseling score (0-100)
   - calc_newborn_visit_score: Newborn care score (0-100)
   - has_all_tools: 'yes'/'no' - Tool availability
   - has_proper_protective_equipment: 'yes'/'no' - PPE availability
   - has_essential_medicines: 'yes'/'no' - Medicine stock

2. family_planning_visits/fp_3months - FP service delivery
   - patient_id, patient_name: Client information
   - county: Service delivery location
   - reported: Service date (2024-12-01 to 2025-06-30)
   - current_fp_method: Method used (COC, POP, condoms, injectable, etc.)
   - on_fp: 'yes'/'no' - Currently using FP
   - has_side_effects: 'yes'/'no' - Side effects reported
   - is_referral: 'yes'/'no' - Referred to facility
   - patient_age_in_years: Client age
   - coc_cycles, pop_cycles, condom_pieces: Commodities provided

3. households - Household registration
   - household_uuid, household_name: Household identifiers
   - chw_uuid: Assigned CHW
   - county: Kisumu, Busia, Vihiga
   - reported_date: Registration date
   - chv_uuid, chv_name: CHW details

4. chw_master/active_chps - CHW information
   - chw_uuid, chw_name: CHW identifiers
   - county_name: Kisumu, Busia, Vihiga
   - chw_phone: Contact information
   - cha_name: CHA supervisor
   - community_unit: Service area

5. u2pop - Under-2 population data
   - county: Population location
   - u2_pop: Under-2 population count
   - reportedm: Reporting period

6. homevisit_1month/homevisit_3month - Home visit tracking
   - family_id: Visited family
   - chw_uuid: Visiting CHW
   - reported: Visit date
   - county: Visit location

QUERY GENERATION RULES:

1. ALWAYS filter by the three main counties when geographic analysis is needed:
   WHERE county IN ('Kisumu', 'Busia', 'Vihiga')

2. ALWAYS filter by the data period when time analysis is needed:
   WHERE reported >= '2024-12-01' AND reported <= '2025-06-30'

3. Performance categorization standards:
   - Excellent: ≥85%
   - Good: 70-84%
   - Needs Improvement: 50-69%
   - Critical: <50%

4. Use CASE statements for performance categories:
   CASE 
       WHEN calc_assessment_score >= 85 THEN 'Excellent'
       WHEN calc_assessment_score >= 70 THEN 'Good'
       WHEN calc_assessment_score >= 50 THEN 'Needs Improvement'
       WHEN calc_assessment_score < 50 THEN 'Critical'
       ELSE 'Unscored'
   END as performance_category

5. Common aggregations:
   - AVG(calc_assessment_score) for mean performance
   - COUNT(DISTINCT chv_uuid) for CHW counts
   - COUNT(*) for total records
   - STDDEV(calc_assessment_score) for performance variance

EXAMPLE QUERIES FOR COMMON SCENARIOS:

Q: "Average supervision scores by county for 2025"
A: SELECT county, 
          AVG(calc_assessment_score) as avg_score,
          COUNT(DISTINCT chv_uuid) as total_chws,
          COUNT(*) as total_supervisions
   FROM supervision 
   WHERE county IN ('Kisumu', 'Busia', 'Vihiga')
     AND reported >= '2025-01-01' AND reported <= '2025-06-30'
     AND calc_assessment_score IS NOT NULL
   GROUP BY county 
   ORDER BY avg_score DESC;

Q: "CHWs in Busia needing retraining based on low family planning scores"
A: SELECT chv_name, chv_uuid,
          AVG(calc_family_planning_score) as avg_fp_score,
          COUNT(*) as supervision_count,
          MAX(reported) as last_supervision
   FROM supervision 
   WHERE county = 'Busia'
     AND reported >= '2024-12-01' AND reported <= '2025-06-30'
     AND calc_family_planning_score IS NOT NULL
     AND calc_family_planning_score < 60
   GROUP BY chv_name, chv_uuid
   ORDER BY avg_fp_score ASC
   LIMIT 20;

Q: "Monthly trends in immunization scores across all three counties"
A: SELECT DATE_TRUNC('month', reported) as month,
          county,
          AVG(calc_immunization_score) as avg_immunization_score,
          COUNT(DISTINCT chv_uuid) as active_chws
   FROM supervision 
   WHERE county IN ('Kisumu', 'Busia', 'Vihiga')
     AND reported >= '2024-12-01' AND reported <= '2025-06-30'
     AND calc_immunization_score IS NOT NULL
   GROUP BY DATE_TRUNC('month', reported), county
   ORDER BY month, county;

Q: "Family planning method distribution in Kisumu"
A: SELECT current_fp_method,
          COUNT(*) as clients,
          COUNT(CASE WHEN has_side_effects = 'yes' THEN 1 END) as side_effects_count,
          ROUND(AVG(patient_age_in_years), 1) as avg_age
   FROM family_planning_visits 
   WHERE county = 'Kisumu'
     AND reported >= '2024-12-01' AND reported <= '2025-06-30'
     AND current_fp_method IS NOT NULL
   GROUP BY current_fp_method
   ORDER BY clients DESC;

QUALITY CHECKS:
- Always include NULL checks for score columns
- Use proper date formatting and bounds
- Include meaningful column aliases
- Add appropriate LIMIT clauses (default 100)
- Order results logically (worst performance first for problem identification)

Return ONLY the SQL query, no explanations or markdown formatting."""

    return AssistantAgent(
        name="sql_generator",
        model_client=model_client,
        system_message=system_message
    )


def execute_sql_query_simple(sql_query):
    """Execute SQL and return DataFrame"""
    try:
        df = execute_sql_query(None, sql_query)
        if df is not None and not df.empty:
            return df
        else:
            return pd.DataFrame({"message": ["No data found for this query"]})
    except Exception as e:
        return pd.DataFrame({"error": [f"SQL execution failed: {str(e)}"]})


def create_analysis_agent():
    """Create analysis agent using AutoGen 0.6+ with strategic client"""
    model_client = get_model_client('report')  # Use fast Groq for analysis
    if not model_client:
        return None

    system_message = """You are a senior health data analyst specializing in Kenya's community health system, with expertise in analyzing CHW performance data from Kisumu, Busia, and Vihiga counties (December 2024 to June 2025 period).

YOUR ROLE: Transform raw data into actionable insights for health officials, CHW supervisors, and county health management teams.

CONTEXT & STANDARDS:
- Data Period: December 2024 - June 2025 (7-month analysis window)
- Geographic Focus: Kisumu, Busia, Vihiga counties
- Performance Benchmarks:
  * Excellent: ≥85% (meets international standards)
  * Good: 70-84% (acceptable performance)
  * Needs Improvement: 50-69% (requires support)
  * Critical: <50% (immediate intervention needed)

ANALYTICAL FRAMEWORK:

1. PERFORMANCE ASSESSMENT:
   - Compare against benchmarks and peer counties
   - Identify trends and patterns over the 7-month period
   - Calculate variance and consistency metrics
   - Flag outliers and exceptional cases

2. ROOT CAUSE ANALYSIS:
   - Link performance to resource availability (tools, PPE, medicines)
   - Consider workload factors (households per CHW, visit frequency)
   - Analyze training and supervision patterns
   - Identify systemic vs. individual issues

3. HEALTH SERVICE AREAS:
   - Pneumonia: Case management, referrals, treatment protocols
   - Malaria: Prevention, testing, treatment adherence
   - Family Planning: Method mix, counseling quality, follow-up
   - Immunization: Coverage, dropout rates, cold chain
   - Nutrition: Growth monitoring, counseling, supplementation
   - Newborn Care: Essential care practices, danger sign recognition

4. COUNTY-SPECIFIC INSIGHTS:
   - Kisumu: Urban-rural mix, high population density, referral patterns
   - Busia: Border dynamics, cross-border health seeking, resource constraints
   - Vihiga: High population density, limited facilities, community engagement

ANALYSIS APPROACH:

When analyzing supervision data:
- "Kisumu shows an average supervision score of 78.2%, which is GOOD performance but below the 85% excellence threshold. This represents a 5.3% improvement from December 2024, indicating positive momentum."

When analyzing performance gaps:
- "23 CHWs in Busia scored below 50% in family planning services, indicating CRITICAL need for targeted FP training. Key gaps include: method counseling (avg 42%), side effect management (avg 38%), and follow-up protocols (avg 41%)."

When analyzing trends:
- "Vihiga demonstrates consistent improvement in immunization scores: Dec 2024 (67%) → June 2025 (79%), representing 18% relative improvement. This correlates with the intensive supervision program launched in February 2025."

When analyzing resource constraints:
- "Tool availability analysis reveals 34% of CHWs in Busia lack essential tools, compared to 18% in Kisumu and 22% in Vihiga. This correlates strongly with lower pneumonia management scores (r=0.73, p<0.001)."

RECOMMENDATION FRAMEWORK:

IMMEDIATE ACTIONS (0-30 days):
- Specific CHWs requiring urgent mentorship
- Critical resource gaps needing immediate attention
- Quality issues requiring supervisor intervention

SHORT-TERM INTERVENTIONS (1-3 months):
- Targeted training programs by service area
- Resource procurement and distribution plans
- Supervision schedule adjustments

MEDIUM-TERM STRATEGIES (3-6 months):
- System-wide capacity building initiatives
- Performance improvement collaboratives
- Resource allocation optimization

REPORTING STYLE:
- Lead with key findings and their significance
- Use specific numbers with context and interpretation
- Provide actionable recommendations with clear timelines
- Reference best practices and evidence-based interventions
- Include confidence levels and data quality notes when relevant

EXAMPLE COMPREHENSIVE ANALYSIS:

"EXECUTIVE SUMMARY: Analysis of 847 supervision records from Kisumu, Busia, and Vihiga (Dec 2024-June 2025) reveals mixed performance with clear improvement opportunities.

KEY FINDINGS:
• Overall Performance: Kisumu leads (78.2% avg), followed by Vihiga (74.1%) and Busia (69.8%)
• Critical Areas: 31 CHWs across all counties scored <50% and require immediate intervention
• Strongest Service: Immunization scores improved 12% system-wide (67%→75%)
• Weakest Service: Family planning remains below benchmark in all counties (avg 63%)
• Resource Gaps: 28% of CHWs lack essential tools, highest in Busia (34%)

ACTIONABLE RECOMMENDATIONS:
1. IMMEDIATE (Next 30 days): Provide intensive mentorship to 31 critically performing CHWs
2. SHORT-TERM (Next 90 days): Implement targeted FP training in all three counties
3. MEDIUM-TERM (Next 6 months): Address tool shortages through coordinated procurement

IMPACT PROJECTION: Implementing these recommendations could improve overall system performance by 15-20% within 6 months, bringing all counties above 80% average."

Always provide specific, evidence-based insights that enable decision-makers to take concrete action."""

    return AssistantAgent(
        name="analysis_agent",
        model_client=model_client,
        system_message=system_message
    )


def create_visualization_agent():
    """Create visualization agent using AutoGen 0.6+ with strategic client"""
    model_client = get_model_client('report')  # Use fast Groq for visualization
    if not model_client:
        return None

    system_message = """You are a data visualization specialist for Kenya health system analysis, focusing on Kisumu, Busia, and Vihiga counties (December 2024 - June 2025 data).

VISUALIZATION STRATEGY FRAMEWORK:

PURPOSE-DRIVEN CHART SELECTION:
1. PERFORMANCE COMPARISON → Horizontal bar charts with benchmark lines
2. TREND ANALYSIS → Line charts with month-over-month progression
3. GEOGRAPHIC ANALYSIS → County comparison charts with color coding
4. DISTRIBUTION ANALYSIS → Histograms and box plots for score distributions
5. CORRELATION ANALYSIS → Scatter plots for relationship identification
6. RESOURCE ANALYSIS → Stacked bar charts for availability metrics

KENYA HEALTH-SPECIFIC VISUALIZATIONS:

FOR SUPERVISION PERFORMANCE DATA:
- Chart Type: Horizontal bar chart with performance bands
- X-axis: Average supervision score (0-100 scale)
- Y-axis: CHW names or county names
- Color Scheme: 
  * Red (<50%): Critical - immediate intervention
  * Orange (50-69%): Needs improvement
  * Yellow (70-84%): Good performance
  * Green (85%+): Excellent performance
- Add benchmark line at 70% (minimum acceptable)
- Add aspiration line at 85% (excellence target)
- Title: "CHW Supervision Performance - [County] ([Month] 2024/2025)"

FOR TEMPORAL TRENDS:
- Chart Type: Multi-line chart with markers
- X-axis: Month (Dec 2024 to Jun 2025)
- Y-axis: Performance score (0-100)
- Lines: One per county (Kisumu=blue, Busia=green, Vihiga=orange)
- Add trend lines and confidence intervals
- Highlight significant changes with annotations
- Title: "7-Month Performance Trends by County (Dec 2024 - Jun 2025)"

FOR SERVICE AREA COMPARISON:
- Chart Type: Radar/spider chart or grouped bar chart
- Services: Pneumonia, Malaria, Family Planning, Immunization, Nutrition, Newborn
- Show county comparison on same chart
- Use consistent color scheme for counties
- Add benchmark rings at 50%, 70%, 85%
- Title: "Service Area Performance Profile - [County Name]"

FOR FAMILY PLANNING ANALYSIS:
- Chart Type: Stacked bar chart with secondary axis
- Primary axis: Number of clients by method (COC, POP, Injectable, Condoms)
- Secondary axis: Side effect rate (line overlay)
- Color code methods consistently
- Add data labels for precise values
- Title: "Family Planning Method Mix and Side Effect Rates - [County]"

FOR RESOURCE AVAILABILITY:
- Chart Type: Grouped bar chart with percentage scale
- Categories: Tools, PPE, Essential Medicines
- Groups: Kisumu, Busia, Vihiga
- Show availability percentage (0-100%)
- Add target line at 90% availability
- Use traffic light colors for clarity
- Title: "Resource Availability by County ([Month] 2025)"

FOR CHW WORKLOAD ANALYSIS:
- Chart Type: Scatter plot with trend line
- X-axis: Number of households per CHW
- Y-axis: Average supervision score
- Point size: Number of supervisions
- Color: County (consistent with other charts)
- Add correlation coefficient and p-value
- Title: "CHW Workload vs. Performance Correlation"

ADVANCED VISUALIZATION RECOMMENDATIONS:

FOR PERFORMANCE DISTRIBUTION:
- Chart Type: Box plot with violin overlay
- Show quartiles, median, outliers for each county
- Add mean markers for comparison
- Include sample size annotations
- Highlight outlier CHWs for follow-up
- Title: "Supervision Score Distribution by County"

FOR IMPROVEMENT TRACKING:
- Chart Type: Before/after comparison with connecting lines
- Show December 2024 vs June 2025 scores
- Connect individual CHW scores with lines
- Color lines by improvement (green) or decline (red)
- Add summary statistics in legend
- Title: "7-Month Performance Change by CHW"

FOR PREDICTIVE ANALYSIS:
- Chart Type: Forecast line chart with confidence bands
- Extend trend lines 3-6 months into future
- Show different scenarios (best case, likely, worst case)
- Add intervention markers where programs started
- Include uncertainty bounds
- Title: "Performance Projection with Intervention Scenarios"

CHART FORMATTING STANDARDS:
- Font: Arial or Roboto, minimum 10pt
- Colors: Colorblind-friendly palette
- Grid lines: Light gray, not distracting
- Data labels: Include when space permits
- Legends: Position to avoid data overlap
- Annotations: Use for key insights and benchmarks

INTERACTIVE FEATURES:
- Hover tooltips with detailed information
- Clickable legends for filtering
- Date range selectors for temporal charts
- County filters for focused analysis
- Export options (PNG, PDF, Excel)

DASHBOARD INTEGRATION:
- Consistent aspect ratios (16:9 or 4:3)
- Coordinated color schemes across charts
- Responsive design for mobile viewing
- Loading states for data refresh
- Error handling for missing data

EXAMPLE RECOMMENDATION:
"For CHW supervision scores by county, I recommend a horizontal bar chart with:
- X-axis: Average supervision score (0-100 scale)
- Y-axis: County names (Kisumu, Busia, Vihiga)  
- Color coding: Red (<50%), Orange (50-69%), Yellow (70-84%), Green (85%+)
- Add benchmark line at 70% (minimum standard)
- Add target line at 85% (excellence goal)
- Include data labels showing exact percentages
- Title: 'County Supervision Performance - Dec 2024 to Jun 2025'
- Subtitle: 'Benchmarked against national standards (n=847 supervisions)'

This visualization immediately shows county rankings, performance against standards, and areas needing attention."

Always specify exact chart configuration, color schemes, axis labels, and formatting details."""

    return AssistantAgent(
        name="viz_agent",
        model_client=model_client,
        system_message=system_message
    )


def run_simple_query_fallback(user_question, db_connection):
    """Fallback function when agents can't be created (no API key)"""
    result = {
        "sql_query": "-- Mock query for demonstration",
        "df": pd.DataFrame({"message": ["Demo mode: No API key configured"]}),
        "summary": f"Demo response for: {user_question}. This would analyze Kenya health data for Kisumu, Busia, and Vihiga counties.",
        "chart": None,
        "chart_suggestion": "Bar chart showing county performance comparison",
        "analysis_metadata": {
            "counties_analyzed": ["Kisumu", "Busia", "Vihiga"],
            "time_period": "Dec 2024 - Jun 2025",
            "data_quality": "demo",
            "analysis_type": "mock"
        }
    }
    return result


def create_chart_from_data(df, chart_suggestion, title="Kenya Health System Analysis"):
    """Create sophisticated Plotly chart based on agent suggestion and data for Kisumu, Busia, Vihiga"""
    
    if df is None or df.empty:
        return None
    
    try:
        # Color scheme for consistent county representation
        county_colors = {
            'Kisumu': '#1f77b4',    # Blue
            'Busia': '#ff7f0e',     # Orange  
            'Vihiga': '#2ca02c',    # Green
            'System Average': '#d62728'  # Red for benchmarks
        }
        
        # Performance color scheme for scores
        performance_colors = {
            'excellent': '#2ca02c',      # Green (≥85%)
            'good': '#ffcc00',           # Yellow (70-84%)
            'needs_improvement': '#ff7f0e',  # Orange (50-69%)
            'critical': '#d62728'        # Red (<50%)
        }
        
        suggestion_lower = chart_suggestion.lower()
        
        # County comparison bar chart
        if ("bar" in suggestion_lower or "county" in suggestion_lower) and "county" in df.columns:
            # Determine the score column
            score_col = None
            for col in df.columns:
                if any(keyword in col.lower() for keyword in ['score', 'avg', 'rate', 'percentage']):
                    score_col = col
                    break
            
            if score_col:
                # Create horizontal bar chart with performance color coding
                fig = go.Figure()
                
                for _, row in df.iterrows():
                    county = row['county']
                    score = row[score_col]
                    
                    # Determine color based on performance
                    if score >= 85:
                        color = performance_colors['excellent']
                        category = 'Excellent (≥85%)'
                    elif score >= 70:
                        color = performance_colors['good']
                        category = 'Good (70-84%)'
                    elif score >= 50:
                        color = performance_colors['needs_improvement']
                        category = 'Needs Improvement (50-69%)'
                    else:
                        color = performance_colors['critical']
                        category = 'Critical (<50%)'
                    
                    fig.add_trace(go.Bar(
                        y=[county],
                        x=[score],
                        name=category,
                        marker_color=color,
                        orientation='h',
                        text=f'{score:.1f}%',
                        textposition='auto',
                        showlegend=False,
                        hovertemplate=f'<b>{county}</b><br>{score_col}: {score:.1f}%<br>Category: {category}<extra></extra>'
                    ))
                
                # Add benchmark lines
                fig.add_vline(x=70, line_dash="dash", line_color="orange", 
                             annotation_text="Minimum Standard (70%)")
                fig.add_vline(x=85, line_dash="dash", line_color="green", 
                             annotation_text="Excellence Target (85%)")
                
                fig.update_layout(
                    title=f"{title}<br><sub>Performance Benchmarked Against National Standards</sub>",
                    xaxis_title=score_col.replace('_', ' ').title(),
                    yaxis_title="County",
                    height=400,
                    font=dict(family="Arial", size=12),
                    plot_bgcolor='white',
                    paper_bgcolor='white'
                )
                
                return fig
        
        # Time series trend chart
        elif ("line" in suggestion_lower or "trend" in suggestion_lower or "time" in suggestion_lower):
            time_cols = [col for col in df.columns if any(keyword in col.lower() for keyword in ['month', 'date', 'time', 'period'])]
            score_cols = [col for col in df.columns if any(keyword in col.lower() for keyword in ['score', 'avg', 'rate'])]
            
            if time_cols and score_cols and 'county' in df.columns:
                time_col = time_cols[0]
                score_col = score_cols[0]
                
                fig = go.Figure()
                
                for county in df['county'].unique():
                    if county in county_colors:
                        county_data = df[df['county'] == county].sort_values(time_col)
                        
                        fig.add_trace(go.Scatter(
                            x=county_data[time_col],
                            y=county_data[score_col],
                            mode='lines+markers',
                            name=county,
                            line=dict(color=county_colors[county], width=3),
                            marker=dict(size=8, color=county_colors[county]),
                            hovertemplate=f'<b>{county}</b><br>Month: %{{x}}<br>Score: %{{y:.1f}}%<extra></extra>'
                        ))
                
                # Add benchmark lines
                fig.add_hline(y=70, line_dash="dash", line_color="orange", 
                             annotation_text="Minimum Standard (70%)")
                fig.add_hline(y=85, line_dash="dash", line_color="green", 
                             annotation_text="Excellence Target (85%)")
                
                fig.update_layout(
                    title=f"{title}<br><sub>7-Month Performance Trends (Dec 2024 - Jun 2025)</sub>",
                    xaxis_title="Month",
                    yaxis_title=score_col.replace('_', ' ').title(),
                    height=500,
                    font=dict(family="Arial", size=12),
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    legend=dict(x=0, y=1, bgcolor='rgba(255,255,255,0.8)')
                )
                
                return fig
        
        # Service area radar/spider chart
        elif ("radar" in suggestion_lower or "spider" in suggestion_lower or "service" in suggestion_lower):
            service_cols = [col for col in df.columns if any(service in col.lower() 
                          for service in ['pneumonia', 'malaria', 'family_planning', 'immunization', 'nutrition', 'newborn'])]
            
            if service_cols and 'county' in df.columns:
                fig = go.Figure()
                
                for county in df['county'].unique():
                    if county in county_colors:
                        county_data = df[df['county'] == county].iloc[0]
                        
                        # Prepare data for radar chart
                        values = [county_data[col] for col in service_cols]
                        labels = [col.replace('_', ' ').replace('avg ', '').title() for col in service_cols]
                        
                        fig.add_trace(go.Scatterpolar(
                            r=values,
                            theta=labels,
                            fill='toself',
                            name=county,
                            line_color=county_colors[county],
                            fillcolor=county_colors[county].replace('1.0', '0.1')  # Semi-transparent fill
                        ))
                
                fig.update_layout(
                    polar=dict(
                        radialaxis=dict(
                            visible=True,
                            range=[0, 100],
                            ticksuffix='%'
                        )),
                    showlegend=True,
                    title=f"{title}<br><sub>Service Area Performance Profile by County</sub>",
                    height=600,
                    font=dict(family="Arial", size=12)
                )
                
                return fig
        
        # Family planning method distribution
        elif ("family planning" in suggestion_lower or "fp" in suggestion_lower or "method" in suggestion_lower):
            method_cols = [col for col in df.columns if any(method in col.lower() 
                         for method in ['coc', 'pop', 'injectable', 'condom'])]
            
            if method_cols and 'county' in df.columns:
                fig = make_subplots(
                    rows=1, cols=len(df['county'].unique()),
                    subplot_titles=df['county'].unique(),
                    specs=[[{'type': 'pie'}] * len(df['county'].unique())]
                )
                
                for i, county in enumerate(df['county'].unique(), 1):
                    county_data = df[df['county'] == county].iloc[0]
                    
                    methods = []
                    values = []
                    for col in method_cols:
                        if county_data[col] > 0:
                            methods.append(col.replace('_users', '').upper())
                            values.append(county_data[col])
                    
                    fig.add_trace(go.Pie(
                        labels=methods,
                        values=values,
                        name=county,
                        textinfo='label+percent',
                        textposition='auto'
                    ), row=1, col=i)
                
                fig.update_layout(
                    title=f"{title}<br><sub>Family Planning Method Distribution by County</sub>",
                    height=400,
                    font=dict(family="Arial", size=12)
                )
                
                return fig
        
        # Resource availability stacked bar
        elif ("resource" in suggestion_lower or "tool" in suggestion_lower or "availability" in suggestion_lower):
            resource_cols = [col for col in df.columns if any(resource in col.lower() 
                           for resource in ['tools', 'ppe', 'medicine', 'equipment'])]
            
            if resource_cols and 'county' in df.columns:
                fig = go.Figure()
                
                colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
                
                for i, col in enumerate(resource_cols):
                    fig.add_trace(go.Bar(
                        x=df['county'],
                        y=df[col],
                        name=col.replace('_availability_rate', '').replace('_', ' ').title(),
                        marker_color=colors[i % len(colors)],
                        text=df[col].apply(lambda x: f'{x:.1f}%'),
                        textposition='auto'
                    ))
                
                # Add target line
                fig.add_hline(y=90, line_dash="dash", line_color="green", 
                             annotation_text="Target (90%)")
                
                fig.update_layout(
                    title=f"{title}<br><sub>Resource Availability Assessment by County</sub>",
                    xaxis_title="County",
                    yaxis_title="Availability Rate (%)",
                    barmode='group',
                    height=500,
                    font=dict(family="Arial", size=12),
                    plot_bgcolor='white',
                    paper_bgcolor='white'
                )
                
                return fig
        
        # Default fallback: simple bar chart
        else:
            if len(df.columns) >= 2:
                fig = px.bar(
                    df, 
                    x=df.columns[0], 
                    y=df.columns[1], 
                    title=title,
                    color=df.columns[0] if 'county' in df.columns[0].lower() else None,
                    color_discrete_map=county_colors if 'county' in df.columns[0].lower() else None
                )
                
                fig.update_layout(
                    height=400,
                    font=dict(family="Arial", size=12),
                    plot_bgcolor='white',
                    paper_bgcolor='white'
                )
                
                return fig
            
    except Exception as e:
        logger.error(f"Chart creation error: {e}")
        return None
    
    return None


def extract_content_from_response(response):
    """Optimized response content extraction"""
    if response is None:
        return None

    # Handle AutoGen Response objects
    if hasattr(response, 'chat_message'):
        chat_message = response.chat_message
        if hasattr(chat_message, 'content'):
            return chat_message.content
        else:
            return str(chat_message)
    elif hasattr(response, 'content'):
        return response.content
    elif isinstance(response, str):
        return response
    elif isinstance(response, list) and len(response) > 0:
        last_response = response[-1]
        if hasattr(last_response, 'chat_message'):
            chat_message = last_response.chat_message
            if hasattr(chat_message, 'content'):
                return chat_message.content
        elif hasattr(last_response, 'content'):
            return last_response.content
        else:
            return str(last_response)
    else:
        return str(response)


def clean_sql_query(sql_content):
    """Clean and validate SQL query"""
    sql_query = sql_content.strip()
    if sql_query.startswith("```sql"):
        sql_query = sql_query.replace("```sql", "").replace("```", "").strip()
    elif sql_query.startswith("```"):
        sql_query = sql_query.replace("```", "").strip()
    return sql_query


def extract_metadata_fast(df, result):
    """Fast metadata extraction from DataFrame"""
    if 'county' in df.columns:
        result["analysis_metadata"]["counties_analyzed"] = df['county'].unique().tolist()

    # Determine analysis type
    if any(col in df.columns for col in ['month', 'report_month', 'reported']):
        result["analysis_metadata"]["analysis_type"] = "temporal_analysis"
    elif 'county' in df.columns and len(df['county'].unique()) > 1:
        result["analysis_metadata"]["analysis_type"] = "county_comparison"
    elif any('score' in col.lower() for col in df.columns):
        result["analysis_metadata"]["analysis_type"] = "performance_analysis"
    else:
        result["analysis_metadata"]["analysis_type"] = "general_query"

    # Quick data quality assessment
    null_percentage = df.isnull().sum().sum() / (len(df) * len(df.columns)) * 100
    if null_percentage < 5:
        result["analysis_metadata"]["data_quality"] = "high"
    elif null_percentage < 15:
        result["analysis_metadata"]["data_quality"] = "medium"
    else:
        result["analysis_metadata"]["data_quality"] = "low"


def create_analysis_context_optimized(user_question, df, result):
    """Create optimized analysis context with reduced size"""
    return f"""
    KENYA HEALTH DATA ANALYSIS: {user_question}

    RESULTS: {len(df)} records, {len(df.columns)} columns
    Counties: {result["analysis_metadata"]["counties_analyzed"]}
    Type: {result["analysis_metadata"]["analysis_type"]}
    Quality: {result["analysis_metadata"]["data_quality"]}

    SAMPLE DATA (first 3 rows):
    {df.head(3).to_string()}

    Provide concise analysis with actionable insights for health officials.
    Focus on performance benchmarks and recommendations.
    """


def create_viz_context_optimized(user_question, df, result):
    """Create optimized visualization context"""
    return f"""
    DATA VISUALIZATION REQUEST for Kenya Health Analysis:

    User Question: {user_question}
    Analysis Type: {result["analysis_metadata"]["analysis_type"]}
    Counties: {', '.join(result["analysis_metadata"]["counties_analyzed"])}

    DATA STRUCTURE:
    - Rows: {len(df)}
    - Columns: {', '.join(df.columns)}

    COLUMN DETAILS:
    {chr(10).join([f"- {col}: {df[col].dtype}" for col in df.columns[:5]])}

    Recommend the most effective visualization with specific formatting details.
    Use county colors: Kisumu=blue, Busia=orange, Vihiga=green.
    Include performance benchmarks (70%, 85% lines) where relevant.
    """


def run_group_chat_optimized(user_question, db_connection):
    """
    Optimized parallel workflow for Kenya health data analysis
    Target: <10s execution time through caching, parallelization, and optimization
    """
    start_time = time.time()

    # Use cached agents for performance
    sql_gen, analyzer, viz_agent = get_cached_agents()

    # If no model client available, use simplified approach
    if not sql_gen or not analyzer or not viz_agent:
        return run_simple_query_fallback(user_question, db_connection)

    # Enhanced result storage with metadata
    result = {
        "sql_query": None,
        "df": None,
        "summary": None,
        "chart": None,
        "chart_suggestion": None,
        "analysis_metadata": {
            "counties_analyzed": [],
            "time_period": "Dec 2024 - Jun 2025",
            "data_quality": "unknown",
            "analysis_type": "unknown"
        }
    }

    try:
        # Step 1: Optimized SQL Generation with reduced context
        logger = logging.getLogger(__name__)
        logger.info(f"Generating SQL for query: {user_question[:50]}...")

        sql_start = time.time()

        # Simplified context for faster processing
        enhanced_query = f"""
        Generate PostgreSQL query for: "{user_question}"

        Context: Kenya health data (Kisumu, Busia, Vihiga counties, Dec 2024-Jun 2025)
        Tables: chw_master, supervision_data, family_planning_data
        Focus: Performance analysis with benchmarks (85%+ excellent, 70-84% good, <50% critical)
        """

        # Use autogen 0.6+ message format with caching
        sql_response = call_agent_sync(sql_gen, enhanced_query, cache_key_prefix="sql_generator")

        # Optimized response parsing
        sql_content = extract_content_from_response(sql_response)

        if sql_content:
            # Clean and validate SQL
            sql_query = clean_sql_query(sql_content)
            result["sql_query"] = sql_query

            sql_time = time.time() - sql_start
            _performance_metrics['sql_generation_times'].append(sql_time)

            # Record performance metric
            record_performance_metric('sql_generation_time', sql_time, 'seconds', {
                'query_length': len(user_question),
                'sql_length': len(sql_query)
            })

            logger.info(f"SQL generated in {sql_time:.2f}s")

            # Step 2: Execute SQL with enhanced error handling
            logger.info("Executing SQL query...")
            df = execute_sql_query_simple(sql_query)

            if df is not None and not df.empty and 'error' not in df.columns:
                result["df"] = df

                # Quick metadata extraction
                extract_metadata_fast(df, result)

                logger.info(f"Query executed: {len(df)} records retrieved")

                # Step 3 & 4: Parallel Analysis and Visualization
                logger.info("Running parallel analysis and visualization...")

                analysis_start = time.time()

                # Prepare optimized contexts
                analysis_context = create_analysis_context_optimized(user_question, df, result)
                viz_context = create_viz_context_optimized(user_question, df, result)

                # Run analysis and visualization in parallel with caching
                with ThreadPoolExecutor(max_workers=2) as executor:
                    # Submit both tasks with caching
                    analysis_future = executor.submit(call_agent_sync, analyzer, analysis_context, "analyzer")
                    viz_future = executor.submit(call_agent_sync, viz_agent, viz_context, "visualizer")

                    # Collect results as they complete
                    for future in as_completed([analysis_future, viz_future]):
                        if future == analysis_future:
                            analysis_response = future.result()
                            result["summary"] = extract_content_from_response(analysis_response)
                            if result["summary"]:
                                logger.info("Analysis completed")
                        elif future == viz_future:
                            viz_response = future.result()
                            result["chart_suggestion"] = extract_content_from_response(viz_response)
                            if result["chart_suggestion"]:
                                logger.info("Visualization recommendation generated")

                analysis_time = time.time() - analysis_start
                _performance_metrics['analysis_times'].append(analysis_time)

                # Record performance metrics
                record_performance_metric('analysis_time', analysis_time, 'seconds', {
                    'data_rows': len(df),
                    'data_columns': len(df.columns),
                    'analysis_type': result["analysis_metadata"]["analysis_type"]
                })

                # Step 5: Quick Chart Creation
                chart = create_chart_from_data(df, result["chart_suggestion"] or "bar chart", user_question)
                result["chart"] = chart

                if chart:
                    logger.info("Chart created successfully")
                else:
                    logger.warning("Chart creation failed, but analysis continues")

            else:
                error_msg = "No data returned from query or query execution failed"
                if df is not None and 'error' in df.columns:
                    error_msg = f"SQL Error: {df['error'].iloc[0] if not df.empty else 'Unknown error'}"

                result["summary"] = f"Query execution issue: {error_msg}. Please try rephrasing your question."
                logger.warning(f"Query execution failed: {error_msg}")

        else:
            result["summary"] = "Unable to generate appropriate SQL query. Please try asking about CHW performance, county comparisons, or family planning services."
            logger.warning("SQL generation failed")

    except Exception as e:
        error_message = f"Analysis workflow error: {str(e)}"
        result["summary"] = f"I encountered an issue while processing your question: {error_message}. Please try a simpler question."
        logger.error(f"Optimized workflow error: {e}")

    # Ensure we always return a meaningful summary
    if not result.get("summary"):
        if result.get("df") is not None and not result["df"].empty:
            result["summary"] = f"Query executed successfully. Retrieved {len(result['df'])} records for analysis."
        else:
            result["summary"] = "Query completed but no actionable insights could be generated from the available data."

    # Add execution metadata
    total_time = time.time() - start_time
    _performance_metrics['total_workflow_times'].append(total_time)

    # Record comprehensive performance metrics
    record_performance_metric('workflow_execution_time', total_time, 'seconds', {
        'user_question_length': len(user_question),
        'has_data': result.get("df") is not None,
        'data_rows': len(result["df"]) if result.get("df") is not None else 0,
        'analysis_type': result["analysis_metadata"]["analysis_type"],
        'counties_analyzed': result["analysis_metadata"]["counties_analyzed"],
        'optimization_features': ["agent_caching", "parallel_processing", "reduced_context"]
    })

    result["execution_metadata"] = {
        "agents_used": ["SQLGenerator", "SQLExecutor", "AnalysisAgent", "VisualizationAgent"],
        "workflow_version": "v2.0_optimized",
        "optimized_for": "Kenya Health System (Kisumu, Busia, Vihiga)",
        "data_period": "December 2024 - June 2025",
        "execution_time": total_time,
        "performance_target": "< 10s",
        "optimization_features": ["agent_caching", "parallel_processing", "reduced_context"]
    }

    logger.info(f"Optimized workflow completed in {total_time:.2f}s")
    return result


def run_group_chat(user_question, db_connection):
    """
    Main function that orchestrates the multi-agent workflow for Kenya health data analysis
    Optimized for Kisumu, Busia, and Vihiga counties data (Dec 2024 - Jun 2025)
    """

    # Use optimized workflow by default
    return run_group_chat_optimized(user_question, db_connection)


def run_interactive_query(user_question, db_connection):
    """
    Interactive query function optimized for fast user responses
    Uses Groq for speed when available, falls back to HuggingFace for stability
    """

    # Create agents with strategic clients for interactive use
    try:
        # SQL generation with stable client (HuggingFace)
        sql_gen = create_sql_generator_agent()

        # Analysis and visualization with fast client (Groq)
        analyzer_client = get_model_client('query')
        viz_client = get_model_client('query')

        if not sql_gen or not analyzer_client or not viz_client:
            logging.warning("Some clients unavailable, using fallback workflow")
            return run_group_chat_optimized(user_question, db_connection)

        # Create analysis and viz agents with fast clients
        analyzer = AssistantAgent(
            name="interactive_analyzer",
            model_client=analyzer_client,
            system_message="You are a fast health data analyst for interactive queries. Provide concise, actionable insights."
        )

        viz_agent = AssistantAgent(
            name="interactive_visualizer",
            model_client=viz_client,
            system_message="You are a visualization specialist for interactive queries. Recommend clear, simple charts."
        )

        # Run optimized workflow with interactive agents
        return run_optimized_workflow_with_agents(user_question, db_connection, sql_gen, analyzer, viz_agent)

    except Exception as e:
        logging.error(f"Interactive query failed: {e}")
        # Fallback to standard workflow
        return run_group_chat_optimized(user_question, db_connection)


def run_optimized_workflow_with_agents(user_question, db_connection, sql_gen, analyzer, viz_agent):
    """
    Run optimized workflow with provided agents
    """
    start_time = time.time()

    # Enhanced result storage with metadata
    result = {
        "sql_query": None,
        "df": None,
        "summary": None,
        "chart": None,
        "chart_suggestion": None,
        "analysis_metadata": {
            "counties_analyzed": [],
            "time_period": "Dec 2024 - Jun 2025",
            "data_quality": "unknown",
            "analysis_type": "unknown"
        }
    }

    try:
        # Step 1: SQL Generation
        logger = logging.getLogger(__name__)
        logger.info(f"Generating SQL for interactive query: {user_question[:50]}...")

        sql_start = time.time()

        # Simplified context for faster processing
        enhanced_query = f"""
        Generate PostgreSQL query for: "{user_question}"

        Context: Kenya health data (Kisumu, Busia, Vihiga counties, Dec 2024-Jun 2025)
        Tables: chw_master, supervision_data, family_planning_data
        Focus: Performance analysis with benchmarks (85%+ excellent, 70-84% good, <50% critical)
        """

        # Use SQL generator with caching
        sql_response = call_agent_sync(sql_gen, enhanced_query, cache_key_prefix="sql_generator")

        # Parse response
        sql_content = extract_content_from_response(sql_response)

        if sql_content:
            # Clean and validate SQL
            sql_query = clean_sql_query(sql_content)
            result["sql_query"] = sql_query

            sql_time = time.time() - sql_start
            logger.info(f"SQL generated in {sql_time:.2f}s")

            # Step 2: Execute SQL
            logger.info("Executing SQL query...")
            df = execute_sql_query_simple(sql_query)

            if df is not None and not df.empty and 'error' not in df.columns:
                result["df"] = df

                # Quick metadata extraction
                extract_metadata_fast(df, result)

                logger.info(f"Query executed: {len(df)} records retrieved")

                # Step 3 & 4: Parallel Analysis and Visualization
                logger.info("Running parallel analysis and visualization...")

                analysis_start = time.time()

                # Prepare optimized contexts
                analysis_context = create_analysis_context_optimized(user_question, df, result)
                viz_context = create_viz_context_optimized(user_question, df, result)

                # Run analysis and visualization in parallel with caching
                with ThreadPoolExecutor(max_workers=2) as executor:
                    # Submit both tasks with caching
                    analysis_future = executor.submit(call_agent_sync, analyzer, analysis_context, "analyzer")
                    viz_future = executor.submit(call_agent_sync, viz_agent, viz_context, "visualizer")

                    # Collect results as they complete
                    for future in as_completed([analysis_future, viz_future]):
                        if future == analysis_future:
                            analysis_response = future.result()
                            result["summary"] = extract_content_from_response(analysis_response)
                            if result["summary"]:
                                logger.info("Analysis completed")
                        elif future == viz_future:
                            viz_response = future.result()
                            result["chart_suggestion"] = extract_content_from_response(viz_response)
                            if result["chart_suggestion"]:
                                logger.info("Visualization recommendation generated")

                analysis_time = time.time() - analysis_start

                # Step 5: Create Chart
                if result["chart_suggestion"] and result["df"] is not None:
                    try:
                        chart = create_chart_from_data(result["df"], result["chart_suggestion"],
                                                     f"Kenya Health Analysis: {user_question[:50]}...")
                        result["chart"] = chart
                        if chart:
                            logger.info("Chart created successfully")
                    except Exception as e:
                        logger.warning(f"Chart creation failed: {e}")

                # Add execution metadata
                total_time = time.time() - start_time
                result["execution_metadata"] = {
                    "total_time": total_time,
                    "sql_time": sql_time,
                    "analysis_time": analysis_time,
                    "workflow_type": "interactive_optimized"
                }

                logger.info(f"Interactive workflow completed in {total_time:.2f}s")
                return result

            else:
                logger.warning("No data returned from SQL query")
                result["summary"] = "No data found for this query. Please try rephrasing your question."
                return result

        else:
            logger.error("Failed to generate SQL query")
            result["summary"] = "Failed to generate SQL query. Please try rephrasing your question."
            return result

    except Exception as e:
        logger.error(f"Interactive workflow error: {e}")
        result["summary"] = f"Error processing query: {str(e)}"
        return result


def run_group_chat_legacy(user_question, db_connection):
    """
    Legacy sequential workflow (kept for comparison and fallback)
    """

    # Initialize agents with specialized roles
    sql_gen = create_sql_generator_agent()
    analyzer = create_analysis_agent()
    viz_agent = create_visualization_agent()

    # If no model client available, use simplified approach
    if not sql_gen or not analyzer or not viz_agent:
        return run_simple_query_fallback(user_question, db_connection)
    
    # Enhanced result storage with metadata
    result = {
        "sql_query": None,
        "df": None,
        "summary": None,
        "chart": None,
        "chart_suggestion": None,
        "analysis_metadata": {
            "counties_analyzed": [],
            "time_period": "Dec 2024 - Jun 2025",
            "data_quality": "unknown",
            "analysis_type": "unknown"
        }
    }

    try:
        # Step 1: Enhanced SQL Generation with context validation
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Generating SQL for query: {user_question[:100]}...")

        # Add context about the specific counties and time period
        enhanced_query = f"""
        Based on this question about Kenya health data: "{user_question}"

        Context:
        - Focus counties: Kisumu, Busia, Vihiga
        - Data period: December 2024 to June 2025
        - Available data: CHW supervision, family planning services, household coverage
        - Performance benchmarks: Excellent ≥85%, Good 70-84%, Needs Improvement 50-69%, Critical <50%

        Generate an optimized PostgreSQL query that:
        1. Filters for the three target counties when geographic analysis is needed
        2. Uses the correct date range (2024-12-01 to 2025-06-30) for temporal analysis
        3. Includes proper performance categorization
        4. Handles NULL values appropriately
        5. Returns meaningful, actionable results
        """

        # Use autogen 0.6+ message format
        sql_response = call_agent_sync(sql_gen, enhanced_query)

        # Extract content from response with improved handling
        sql_content = None
        if sql_response is None:
            logging.warning("SQL response is None")
        elif hasattr(sql_response, 'content'):
            sql_content = sql_response.content
        elif isinstance(sql_response, str):
            sql_content = sql_response
        elif isinstance(sql_response, list) and len(sql_response) > 0:
            # Handle list responses
            last_item = sql_response[-1]
            if hasattr(last_item, 'content'):
                sql_content = last_item.content
            else:
                sql_content = str(last_item)
        else:
            # Try to convert to string as fallback
            sql_content = str(sql_response)
            logging.warning(f"Unexpected response type: {type(sql_response)}, converted to string")

        if sql_content:
            # Clean and validate SQL
            sql_query = sql_content.strip()
            if sql_query.startswith("```sql"):
                sql_query = sql_query.replace("```sql", "").replace("```", "").strip()
            elif sql_query.startswith("```"):
                sql_query = sql_query.replace("```", "").strip()

            result["sql_query"] = sql_query
            logger.info("SQL query generated successfully")

            # Step 2: Execute SQL with enhanced error handling
            logger.info("Executing SQL query...")
            df = execute_sql_query_simple(sql_query)
            
            if df is not None and not df.empty and 'error' not in df.columns:
                result["df"] = df
                
                # Extract metadata from results
                if 'county' in df.columns:
                    result["analysis_metadata"]["counties_analyzed"] = df['county'].unique().tolist()
                
                # Determine analysis type
                if any(col in df.columns for col in ['month', 'report_month', 'reported']):
                    result["analysis_metadata"]["analysis_type"] = "temporal_analysis"
                elif 'county' in df.columns and len(df['county'].unique()) > 1:
                    result["analysis_metadata"]["analysis_type"] = "county_comparison"
                elif any('score' in col.lower() for col in df.columns):
                    result["analysis_metadata"]["analysis_type"] = "performance_analysis"
                else:
                    result["analysis_metadata"]["analysis_type"] = "general_query"
                
                # Assess data quality
                total_records = len(df)
                null_percentage = df.isnull().sum().sum() / (len(df) * len(df.columns)) * 100
                
                if null_percentage < 5:
                    result["analysis_metadata"]["data_quality"] = "high"
                elif null_percentage < 15:
                    result["analysis_metadata"]["data_quality"] = "medium"
                else:
                    result["analysis_metadata"]["data_quality"] = "low"
                
                logger.info(f"Query executed successfully: {total_records} records retrieved")
                
                # Step 3: Enhanced Analysis with context
                logger.info("Generating comprehensive analysis...")
                
                # Prepare rich context for analysis
                data_summary = f"""
                KENYA HEALTH DATA ANALYSIS REQUEST: {user_question}
                
                QUERY RESULTS SUMMARY:
                - Total records: {len(df)}
                - Columns: {', '.join(df.columns)}
                - Counties in results: {result["analysis_metadata"]["counties_analyzed"]}
                - Analysis type: {result["analysis_metadata"]["analysis_type"]}
                - Data quality: {result["analysis_metadata"]["data_quality"]}
                
                SAMPLE DATA:
                {df.head(10).to_string()}
                
                STATISTICAL SUMMARY:
                {df.describe().to_string() if len(df.select_dtypes(include=['number']).columns) > 0 else "No numerical columns for statistics"}
                
                KEY INSIGHTS TO ANALYZE:
                1. Performance against benchmarks (Excellent ≥85%, Good 70-84%, Critical <50%)
                2. County-specific patterns and gaps
                3. Actionable recommendations for health officials
                4. Resource allocation implications
                5. Training and support needs identification
                
                Please provide a comprehensive analysis with specific, actionable insights.
                """
                
                analysis_response = call_agent_sync(analyzer, data_summary)

                # Extract content from response
                if hasattr(analysis_response, 'content'):
                    result["summary"] = analysis_response.content
                elif isinstance(analysis_response, str):
                    result["summary"] = analysis_response

                if result["summary"]:
                    logger.info("Analysis completed successfully")
                
                # Step 4: Enhanced Visualization Recommendations
                logger.info("Generating visualization recommendations...")
                
                viz_context = f"""
                DATA VISUALIZATION REQUEST for Kenya Health Analysis:
                
                User Question: {user_question}
                Analysis Type: {result["analysis_metadata"]["analysis_type"]}
                Counties: {', '.join(result["analysis_metadata"]["counties_analyzed"])}
                
                DATA STRUCTURE:
                - Rows: {len(df)}
                - Columns: {', '.join(df.columns)}
                
                COLUMN DETAILS:
                {chr(10).join([f"- {col}: {df[col].dtype} ({'numeric' if df[col].dtype in ['int64', 'float64'] else 'categorical'})" for col in df.columns])}
                
                VISUALIZATION REQUIREMENTS:
                1. Must be appropriate for Kenya health system stakeholders
                2. Should use county-specific color coding (Kisumu=blue, Busia=orange, Vihiga=green)
                3. Include performance benchmarks where relevant (70%, 85% lines)
                4. Be professionally formatted for health officials
                5. Support decision-making and action planning
                
                Please recommend the most effective visualization approach with specific formatting details.
                """
                
                viz_response = call_agent_sync(viz_agent, viz_context)

                # Extract content from response
                viz_content = None
                if hasattr(viz_response, 'content'):
                    viz_content = viz_response.content
                elif isinstance(viz_response, str):
                    viz_content = viz_response

                if viz_content:
                    result["chart_suggestion"] = viz_content
                    logger.info("Visualization recommendation generated")

                # Step 5: Create Enhanced Chart
                chart = create_chart_from_data(df, viz_content or "bar chart", user_question)
                result["chart"] = chart
                
                if chart:
                    logger.info("Chart created successfully")
                else:
                    logger.warning("Chart creation failed, but analysis continues")
            
            else:
                error_msg = "No data returned from query or query execution failed"
                if df is not None and 'error' in df.columns:
                    error_msg = f"SQL Error: {df['error'].iloc[0] if not df.empty else 'Unknown error'}"
                
                result["summary"] = f"Query execution issue: {error_msg}. Please try rephrasing your question or check if the requested data exists in our system."
                logger.warning(f"Query execution failed: {error_msg}")
        
        else:
            result["summary"] = "Unable to generate appropriate SQL query for your question. Please try asking about CHW performance, county comparisons, family planning services, or resource availability."
            logger.warning("SQL generation failed")
    
    except Exception as e:
        error_message = f"Analysis workflow error: {str(e)}"
        result["summary"] = f"I encountered an issue while processing your question: {error_message}. Please try a simpler question or contact support if this persists."
        logger.error(f"Group chat workflow error: {e}")
    
    # Ensure we always return a meaningful summary
    if not result.get("summary"):
        if result.get("df") is not None and not result["df"].empty:
            result["summary"] = f"Query executed successfully. Retrieved {len(result['df'])} records for analysis."
        else:
            result["summary"] = "Query completed but no actionable insights could be generated from the available data."
    
    # Add execution metadata
    result["execution_metadata"] = {
        "agents_used": ["SQLGenerator", "SQLExecutor", "AnalysisAgent", "VisualizationAgent"],
        "workflow_version": "v1.2",
        "optimized_for": "Kenya Health System (Kisumu, Busia, Vihiga)",
        "data_period": "December 2024 - June 2025"
    }
    
    logger.info("Group chat workflow completed successfully")
    return result


def run_simple_query(question, db_connection):
    """Simplified single-agent query for basic questions"""

    sql_gen = create_sql_generator_agent()

    if not sql_gen:
        return run_simple_query_fallback(question, db_connection)

    try:
        # Generate SQL
        sql_response = call_agent_sync(sql_gen, f"Generate SQL for: {question}")

        # Extract content from response with improved handling
        sql_content = None
        if sql_response is None:
            logging.warning("SQL response is None")
        elif hasattr(sql_response, 'content'):
            sql_content = sql_response.content
        elif isinstance(sql_response, str):
            sql_content = sql_response
        elif isinstance(sql_response, list) and len(sql_response) > 0:
            # Handle list responses
            last_item = sql_response[-1]
            if hasattr(last_item, 'content'):
                sql_content = last_item.content
            else:
                sql_content = str(last_item)
        else:
            # Try to convert to string as fallback
            sql_content = str(sql_response)
            logging.warning(f"Unexpected response type: {type(sql_response)}, converted to string")

        if sql_content:
            sql_query = sql_content.strip()
            if sql_query.startswith("```sql"):
                sql_query = sql_query.replace("```sql", "").replace("```", "").strip()

            # Execute query
            df = execute_sql_query_simple(sql_query)

            return {
                "sql_query": sql_query,
                "df": df,
                "summary": f"Found {len(df) if df is not None else 0} records."
            }

    except Exception as e:
        return {
            "sql_query": None,
            "df": None,
            "summary": f"Error: {str(e)}"
        }
