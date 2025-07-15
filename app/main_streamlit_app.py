"""
main_streamlit_app.py - Ushauri AI Kenya Community Health Systems
Enhanced for Kisumu, Busia, and Vihiga counties (December 2024 - June 2025)
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
import logging
from typing import Dict, Any
import json

# Import our custom modules
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import RBAC system
try:
    from security.auth_decorators import (
        protected_page, require_permission, require_role,
        is_authenticated, get_current_user, show_login_page,
        init_auth_system, show_user_info
    )
    from security.rbac import UserRole, Permission
    from security.user_management import show_user_management
    RBAC_ENABLED = os.getenv('RBAC_ENABLED', 'true').lower() == 'true'
except ImportError:
    RBAC_ENABLED = False
    def protected_page(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    def require_permission(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

from autogen_agents.group_chat import run_group_chat, run_simple_query, run_interactive_query

def run_rbac_aware_query(user_query: str, db_connection):
    """Run query with RBAC county access control"""
    if not RBAC_ENABLED:
        return run_interactive_query(user_query, db_connection)  # Use fast interactive query

    user = get_current_user()
    if not user:
        return {"success": False, "error": "Authentication required"}

    # Check if user has permission to run analysis
    from security.rbac import get_rbac_manager
    rbac = get_rbac_manager()

    if not rbac.has_permission(user, Permission.RUN_ANALYSIS):
        return {"success": False, "error": "Permission denied: RUN_ANALYSIS required"}

    # Add county filter to query if user has limited access
    if user.role not in [UserRole.SUPER_ADMIN, UserRole.SYSTEM_ADMIN, UserRole.ME_OFFICER, UserRole.DATA_ANALYST]:
        if user.counties:
            # Add county filter context to the query
            county_context = f"\n\nIMPORTANT: This user can only access data for the following counties: {', '.join(user.counties)}. Please filter all queries to include only these counties."
            user_query = user_query + county_context

    return run_interactive_query(user_query, db_connection)  # Use fast interactive query
from tools.db import connect_db, test_connection, get_dashboard_metrics, check_database_health, execute_sql_query
from tools.report_generator import (
    generate_report, generate_pdf_report_from_result,
    create_monthly_chw_report_pdf, export_data_to_excel
)
from tools.embeddings import (
    search_similar_questions, add_user_query, get_query_suggestions,
    render_query_suggestions_sidebar, initialize_embeddings, get_embedding_stats
)
from tools.queries import (
    run_auto_reports, county_comparison_plot, chw_performance_trend_plot,
    get_dashboard_metrics, execute_predefined_query, get_available_queries,
    get_query_description, PREDEFINED_QUERIES
)
from tools.memory import (
    load_chat_memory, save_chat_memory, get_memory_statistics,
    initialize_session_id, render_memory_sidebar, cleanup_memory_system,
    get_cached_query_result, cache_query_result
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="Ushauri AI - Kenya Health Intelligence",
    page_icon="🇰🇪",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://github.com/your-repo/kenya-agentic-ai',
        'Report a bug': 'https://github.com/your-repo/kenya-agentic-ai/issues',
        'About': "# Ushauri AI\nAdvanced AI assistant for Kenya's health data analysis\nFocused on Kisumu, Busia & Vihiga counties"
    }
)

# Enhanced CSS for professional appearance
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        padding: 2rem;
        border-radius: 15px;
        color: white;
        margin-bottom: 2rem;
        text-align: center;
        box-shadow: 0 8px 32px rgba(0,0,0,0.1);
    }
    
    .county-badge {
        display: inline-block;
        padding: 0.5rem 1rem;
        margin: 0.25rem;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.9rem;
    }
    
    .county-kisumu { background: #e3f2fd; color: #1565c0; border: 2px solid #1976d2; }
    .county-busia { background: #fff3e0; color: #e65100; border: 2px solid #f57c00; }
    .county-vihiga { background: #e8f5e8; color: #2e7d32; border: 2px solid #388e3c; }
    
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 15px;
        border-left: 5px solid #1976d2;
        box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        margin-bottom: 1rem;
        transition: transform 0.2s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(0,0,0,0.12);
    }
    
    .performance-excellent { border-left-color: #4caf50; background: linear-gradient(135deg, #e8f5e8 0%, #f1f8e9 100%); }
    .performance-good { border-left-color: #ff9800; background: linear-gradient(135deg, #fff3e0 0%, #fef7f0 100%); }
    .performance-needs-improvement { border-left-color: #ff5722; background: linear-gradient(135deg, #fbe9e7 0%, #ffebee 100%); }
    .performance-critical { border-left-color: #f44336; background: linear-gradient(135deg, #ffebee 0%, #fce4ec 100%); }
    
    .chat-message {
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1rem 0;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
    }
    
    .user-message {
        background: linear-gradient(135deg, #e3f2fd 0%, #f3e5f5 100%);
        border-left: 4px solid #2196f3;
    }
    
    .assistant-message {
        background: linear-gradient(135deg, #f3e5f5 0%, #e8f5e8 100%);
        border-left: 4px solid #9c27b0;
    }
    
    .insight-box {
        background: linear-gradient(135deg, #fff9c4 0%, #f0f4c3 100%);
        border: 1px solid #dce775;
        border-radius: 10px;
        padding: 1rem;
        margin: 1rem 0;
        border-left: 4px solid #cddc39;
    }
    
    .alert-critical {
        background: linear-gradient(135deg, #ffebee 0%, #fce4ec 100%);
        border: 1px solid #f8bbd9;
        border-radius: 10px;
        padding: 1rem;
        margin: 1rem 0;
        border-left: 4px solid #e91e63;
    }
    
    .quick-action-btn {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 1rem 2rem;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    }
    
    .quick-action-btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4);
    }
    
    .data-period-banner {
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        color: white;
        padding: 0.75rem;
        border-radius: 8px;
        text-align: center;
        font-weight: 600;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Enhanced sample queries specific to the three counties and time period
SAMPLE_QUERIES = {
    "Performance Analysis": [
        "Which CHWs in Busia have the lowest family planning scores in Q2 2025?",
        "Compare pneumonia management scores between Kisumu and Vihiga counties",
        "Show CHWs in all three counties who improved significantly since December 2024",
        "Identify critical performing CHWs requiring immediate intervention",
        "What are the average supervision scores by county for the first half of 2025?"
    ],
    "Trend Analysis": [
        "Show monthly performance trends for Kisumu county from Dec 2024 to June 2025",
        "How did immunization scores change across all counties during this period?",
        "Which county showed the most improvement in overall supervision scores?",
        "Analyze family planning service trends over the 7-month period",
        "Track tool availability changes from December 2024 to June 2025"
    ],
    "Resource & Training": [
        "Which CHWs in Vihiga lack essential tools and medicines?",
        "Show counties with lowest resource availability rates",
        "Identify CHWs needing retraining based on service area performance",
        "Compare resource gaps between the three counties",
        "Which areas have the highest tool shortage rates?"
    ],
    "Service Delivery": [
        "Analyze family planning method distribution across Kisumu, Busia, and Vihiga",
        "Show side effect rates for family planning services by county",
        "Compare household coverage between the three counties",
        "Analyze under-2 population coverage by CHWs",
        "Show referral patterns for family planning services"
    ]
}


def initialize_app():
    """Initialize application state and connections with enhanced error handling"""
    # Initialize session
    initialize_session_id()
    
    # Display data period banner
    st.markdown("""
    <div class="data-period-banner">
        📊 Analysis Period: December 2024 - June 2025 | Focus Counties: Kisumu, Busia, Vihiga
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize embeddings system
    if 'embeddings_initialized' not in st.session_state:
        with st.spinner("🧠 Initializing AI intelligence system..."):
            try:
                st.session_state.embeddings_initialized = initialize_embeddings()
                if st.session_state.embeddings_initialized:
                    st.success("✅ AI system ready")
                else:
                    st.warning("⚠️ AI system running in limited mode")
            except Exception as e:
                st.error(f"❌ AI system initialization failed: {e}")
                st.session_state.embeddings_initialized = False
    
    # Initialize database connection
    if 'db_connection' not in st.session_state:
        with st.spinner("🔗 Connecting to Kenya health database..."):
            try:
                st.session_state.db_connection = connect_db()
                if st.session_state.db_connection:
                    # Test connection with health check
                    from tools.db import check_database_health_detailed
                    health = check_database_health_detailed(st.session_state.db_connection)
                    if health.get("connection"):
                        st.success("✅ Database connected successfully")
                    else:
                        st.error("❌ Database connection unstable")
                else:
                    st.error("❌ Failed to connect to database")
            except Exception as e:
                st.error(f"❌ Database connection error: {e}")
                st.session_state.db_connection = None
    
    # Initialize memory system
    if 'memory_stats' not in st.session_state:
        try:
            st.session_state.memory_stats = get_memory_statistics()
        except Exception as e:
            logger.error(f"Memory initialization error: {e}")
            st.session_state.memory_stats = {}


def render_header():
    """Render main application header with county focus"""
    st.markdown("""
    <div class="main-header">
        <h1>🇰🇪 Ushauri AI: Kenya Health Intelligence</h1>
        <p>Advanced AI-powered assistant for community health data analysis and decision support</p>
        <div style="margin-top: 1rem;">
            <span class="county-badge county-kisumu">Kisumu County</span>
            <span class="county-badge county-busia">Busia County</span>
            <span class="county-badge county-vihiga">Vihiga County</span>
        </div>
        <p style="margin-top: 1rem; font-size: 0.9rem; opacity: 0.9;">
            Comprehensive analysis for 150+ CHWs across 3 counties | December 2024 - June 2025
        </p>
    </div>
    """, unsafe_allow_html=True)


def render_sidebar():
    """Render sidebar with system information and quick actions"""
    with st.sidebar:
        # RBAC-aware navigation
        if RBAC_ENABLED:
            user = get_current_user()
            if user:
                st.markdown("### 👤 User Menu")

                # Generate unique keys for navigation buttons
                if 'nav_button_keys' not in st.session_state:
                    import secrets
                    st.session_state.nav_button_keys = {
                        'user_mgmt': f"nav_user_mgmt_{secrets.token_hex(3)}",
                        'perf_monitor': f"nav_perf_monitor_{secrets.token_hex(3)}",
                        'cache_mgmt': f"nav_cache_mgmt_{secrets.token_hex(3)}"
                    }

                # User management (admin only)
                if user.role in [UserRole.SUPER_ADMIN, UserRole.SYSTEM_ADMIN]:
                    if st.button("👥 User Management", use_container_width=True, key=st.session_state.nav_button_keys['user_mgmt']):
                        st.session_state.page = "user_management"
                        st.rerun()

                # Performance monitoring (admin and M&E officers)
                if user.role in [UserRole.SUPER_ADMIN, UserRole.SYSTEM_ADMIN, UserRole.ME_OFFICER]:
                    if st.button("📊 Performance Monitor", use_container_width=True, key=st.session_state.nav_button_keys['perf_monitor']):
                        st.session_state.page = "performance_monitor"
                        st.rerun()

                # Cache management (admin only)
                if user.role in [UserRole.SUPER_ADMIN, UserRole.SYSTEM_ADMIN]:
                    if st.button("🔄 Cache Management", use_container_width=True, key=st.session_state.nav_button_keys['cache_mgmt']):
                        st.session_state.page = "cache_management"
                        st.rerun()

                st.markdown("---")

        st.markdown("### 🔧 System Status")

        # Database status
        try:
            health = check_database_health()
            if health.get("status") == "healthy":
                st.success("✅ Database Connected")
            else:
                st.error("❌ Database Issues")
        except:
            st.error("❌ Database Error")

        # AI Model status
        try:
            from autogen_agents.group_chat import get_model_client
            client = get_model_client()
            if client:
                st.success("✅ AI Model Ready")
            else:
                st.error("❌ AI Model Issues")
        except:
            st.error("❌ AI Model Error")

        st.markdown("---")

        # Quick stats
        st.markdown("### 📊 Quick Stats")
        try:
            metrics = get_dashboard_metrics()
            st.metric("Total CHWs", metrics.get("total_chws", 0))
            st.metric("Supervisions", metrics.get("total_supervisions", 0))
            st.metric("Avg Score", f"{metrics.get('avg_score', 0):.1f}%")
        except:
            st.info("Loading metrics...")

        st.markdown("---")

        # System info
        st.markdown("### ℹ️ System Info")
        st.markdown("""
        **Model**: Llama-3.1-8B-Instant
        **Provider**: Groq
        **Counties**: Kisumu, Busia, Vihiga
        **Period**: Dec 2024 - Jun 2025
        """)


def render_system_status():
    """Render enhanced system status with health indicators"""
    col1, col2, col3, col4, col5 = st.columns(5)
    
    # Database status
    with col1:
        if st.session_state.db_connection:
            try:
                from tools.db import check_database_health_detailed
                health = check_database_health_detailed(st.session_state.db_connection)
                if health.get("connection") and health.get("data_present"):
                    st.markdown('<div class="metric-card performance-excellent">🟢 Database<br><small>Connected & Healthy</small></div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="metric-card performance-needs-improvement">🟡 Database<br><small>Limited Access</small></div>', unsafe_allow_html=True)
            except:
                st.markdown('<div class="metric-card performance-critical">🔴 Database<br><small>Connection Error</small></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="metric-card performance-critical">🔴 Database<br><small>Disconnected</small></div>', unsafe_allow_html=True)
    
    # AI System status
    with col2:
        if st.session_state.embeddings_initialized:
            st.markdown('<div class="metric-card performance-excellent">🧠 AI System<br><small>Fully Operational</small></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="metric-card performance-needs-improvement">⚠️ AI System<br><small>Limited Mode</small></div>', unsafe_allow_html=True)
    
    # Memory status
    with col3:
        memory_stats = st.session_state.memory_stats
        total_conversations = memory_stats.get("conversations", {}).get("total_conversations", 0)
        if total_conversations > 0:
            st.markdown(f'<div class="metric-card performance-excellent">💾 Memory<br><small>{total_conversations} Conversations</small></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="metric-card performance-good">💾 Memory<br><small>Ready</small></div>', unsafe_allow_html=True)
    
    # Data coverage
    with col4:
        if st.session_state.db_connection:
            try:
                # Quick check for data in the period
                test_query = """
                SELECT COUNT(*) as record_count 
                FROM supervision 
                WHERE county IN ('Kisumu', 'Busia', 'Vihiga')
                AND reported >= '2024-12-01' AND reported <= '2025-06-30'
                """
                result = execute_sql_query(st.session_state.db_connection, test_query)
                if result is not None and not result.empty:
                    count = result['record_count'].iloc[0]
                    if count > 100:
                        st.markdown(f'<div class="metric-card performance-excellent">📊 Data Coverage<br><small>{count:,} Records</small></div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="metric-card performance-needs-improvement">📊 Data Coverage<br><small>{count} Records</small></div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="metric-card performance-critical">📊 Data Coverage<br><small>No Data</small></div>', unsafe_allow_html=True)
            except:
                st.markdown('<div class="metric-card performance-critical">📊 Data Coverage<br><small>Check Failed</small></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="metric-card performance-critical">📊 Data Coverage<br><small>No Connection</small></div>', unsafe_allow_html=True)
    
    # Session info
    with col5:
        session_id = st.session_state.get('session_id', 'unknown')
        st.markdown(f'<div class="metric-card performance-good">🔑 Session<br><small>{session_id}</small></div>', unsafe_allow_html=True)


def render_enhanced_dashboard_metrics():
    """Render comprehensive dashboard metrics for the three counties"""
    if not st.session_state.db_connection:
        st.warning("⚠️ Database connection required for dashboard metrics")
        return
    
    st.subheader("📈 System Performance Dashboard")
    
    try:
        # Get enhanced metrics for the three counties
        metrics_query = """
        SELECT 
            county,
            COUNT(DISTINCT chv_uuid) as total_chws,
            AVG(calc_assessment_score) as avg_score,
            COUNT(*) as total_supervisions,
            COUNT(CASE WHEN calc_assessment_score >= 85 THEN 1 END) as excellent_performers,
            COUNT(CASE WHEN calc_assessment_score < 50 THEN 1 END) as critical_performers,
            MAX(reported) as latest_supervision
        FROM supervision 
        WHERE county IN ('Kisumu', 'Busia', 'Vihiga')
        AND reported >= '2024-12-01' AND reported <= '2025-06-30'
        AND calc_assessment_score IS NOT NULL
        GROUP BY county
        ORDER BY avg_score DESC
        """
        
        county_metrics = execute_sql_query(st.session_state.db_connection, metrics_query)
        
        if county_metrics is not None and not county_metrics.empty:
            # Overall system metrics
            col1, col2, col3, col4 = st.columns(4)
            
            total_chws = county_metrics['total_chws'].sum()
            system_avg = county_metrics['avg_score'].mean()
            total_supervisions = county_metrics['total_supervisions'].sum()
            critical_count = county_metrics['critical_performers'].sum()
            
            with col1:
                st.metric(
                    label="👥 Active CHWs",
                    value=f"{total_chws:,}",
                    help="Total CHWs across Kisumu, Busia, and Vihiga"
                )
            
            with col2:
                score_color = "normal" if system_avg >= 70 else "inverse"
                performance_level = "Excellent" if system_avg >= 85 else "Good" if system_avg >= 70 else "Needs Improvement"
                st.metric(
                    label="📊 System Average Score",
                    value=f"{system_avg:.1f}%",
                    delta=f"{performance_level}",
                    delta_color=score_color,
                    help="Average supervision score across all three counties"
                )
            
            with col3:
                st.metric(
                    label="📋 Total Supervisions",
                    value=f"{total_supervisions:,}",
                    help="Supervision assessments (Dec 2024 - Jun 2025)"
                )
            
            with col4:
                critical_color = "inverse" if critical_count > 0 else "normal"
                st.metric(
                    label="🚨 Critical Performers",
                    value=f"{critical_count}",
                    delta="Need immediate attention" if critical_count > 0 else "All performing well",
                    delta_color=critical_color,
                    help="CHWs with scores below 50% requiring intervention"
                )
            
            # County-specific breakdown
            st.subheader("🏥 County Performance Breakdown")
            
            cols = st.columns(3)
            county_colors = {"Kisumu": "#1f77b4", "Busia": "#ff7f0e", "Vihiga": "#2ca02c"}
            
            for i, (_, county_data) in enumerate(county_metrics.iterrows()):
                with cols[i]:
                    county = county_data['county']
                    score = county_data['avg_score']
                    
                    # Determine performance class
                    if score >= 85:
                        perf_class = "performance-excellent"
                        perf_text = "🌟 Excellent"
                    elif score >= 70:
                        perf_class = "performance-good"
                        perf_text = "✅ Good"
                    elif score >= 50:
                        perf_class = "performance-needs-improvement"
                        perf_text = "⚠️ Needs Improvement"
                    else:
                        perf_class = "performance-critical"
                        perf_text = "🚨 Critical"
                    
                    st.markdown(f"""
                    <div class="metric-card {perf_class}">
                        <h3 style="margin: 0; color: {county_colors[county]};">{county} County</h3>
                        <h2 style="margin: 0.5rem 0;">{score:.1f}%</h2>
                        <p style="margin: 0; font-weight: 600;">{perf_text}</p>
                        <hr style="margin: 1rem 0;">
                        <div style="display: flex; justify-content: space-between;">
                            <span><strong>{county_data['total_chws']}</strong><br><small>CHWs</small></span>
                            <span><strong>{county_data['excellent_performers']}</strong><br><small>Excellent</small></span>
                            <span><strong>{county_data['critical_performers']}</strong><br><small>Critical</small></span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        
        else:
            st.error("❌ Could not load dashboard metrics. Please check database connection.")
    
    except Exception as e:
        st.error(f"❌ Error loading dashboard: {e}")


def render_main_chat_interface():
    """Render the main AI chatbot interface"""
    st.markdown("## 🤖 AI Assistant - Ask Anything About Kenya Health Data")
    st.markdown("**Get instant insights, SQL queries, and analysis from your health data**")

    # Chat input
    col1, col2 = st.columns([4, 1])

    with col1:
        user_query = st.text_input(
            "Ask your question:",
            placeholder="e.g., Show me CHW performance trends in Kisumu county",
            key="chat_input"
        )

    with col2:
        send_button = st.button("🚀 Send", type="primary", use_container_width=True)

    # Quick action buttons
    st.markdown("**Quick Actions:**")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("📊 CHW Performance", use_container_width=True, key="ai_assistant_chw_perf"):
            user_query = "Show me overall CHW performance across all counties"
            send_button = True

    with col2:
        if st.button("🏥 County Comparison", use_container_width=True, key="ai_assistant_county_comp"):
            user_query = "Compare performance between Kisumu, Busia, and Vihiga counties"
            send_button = True

    with col3:
        if st.button("📈 Trends Analysis", use_container_width=True, key="ai_assistant_trends"):
            user_query = "Show me monthly performance trends for the last 6 months"
            send_button = True

    with col4:
        if st.button("⚠️ Critical Issues", use_container_width=True, key="ai_assistant_critical"):
            user_query = "Identify CHWs with critical performance scores needing intervention"
            send_button = True

    # Process query
    if (send_button and user_query) or user_query:
        if user_query.strip():
            with st.spinner("🧠 AI is analyzing your question..."):
                try:
                    # Get database connection
                    db_connection = st.session_state.get('db_connection') or connect_db()

                    # Use the AI system to process the query with RBAC
                    response = run_rbac_aware_query(user_query, db_connection)

                    if response and response.get('success'):
                        # Display the response
                        st.markdown("### 🎯 AI Analysis Results")

                        # Show SQL query if generated
                        if response.get('sql_query'):
                            with st.expander("📝 Generated SQL Query"):
                                st.code(response['sql_query'], language='sql')

                        # Show data results
                        if response.get('data') is not None and not response['data'].empty:
                            st.markdown("#### 📊 Data Results")
                            st.dataframe(response['data'], use_container_width=True)

                            # Download button for data
                            csv = response['data'].to_csv(index=False)
                            st.download_button(
                                label="📥 Download Results as CSV",
                                data=csv,
                                file_name=f"kenya_health_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv"
                            )

                        # Show AI insights
                        if response.get('analysis'):
                            st.markdown("#### 💡 AI Insights")
                            st.markdown(response['analysis'])

                        # Show visualizations if any
                        if response.get('chart'):
                            st.markdown("#### 📈 Visualization")
                            st.plotly_chart(response['chart'], use_container_width=True)

                        # Save to memory
                        save_chat_memory(user_query, response.get('analysis', 'Analysis completed'))

                    else:
                        st.error("❌ Sorry, I couldn't process your question. Please try rephrasing it.")
                        if response.get('error'):
                            st.error(f"Error details: {response['error']}")

                except Exception as e:
                    st.error(f"❌ An error occurred: {str(e)}")
                    logger.error(f"Chat interface error: {e}")

    # Chat history
    st.markdown("---")
    st.markdown("### 📚 Recent Conversations")

    chat_history = load_chat_memory()
    if chat_history:
        for i, (query, response) in enumerate(reversed(chat_history[-5:])):
            with st.expander(f"💬 {query[:80]}..."):
                st.markdown(f"**Question:** {query}")
                st.markdown(f"**Response:** {response[:500]}...")
                if st.button(f"🔄 Ask Again", key=f"repeat_{i}"):
                    st.session_state.chat_input = query
                    st.rerun()
    else:
        st.info("💡 No conversation history yet. Start by asking a question above!")


def render_reports_tab():
    """Render comprehensive reports and analytics"""
    st.markdown("## 📊 Reports & Analytics Dashboard")
    st.markdown("**Generate comprehensive reports and export data for stakeholders**")

    # Report type selection
    report_type = st.selectbox(
        "📋 Select Report Type:",
        [
            "CHW Performance Summary",
            "County Comparison Report",
            "Monthly Trends Analysis",
            "Service Area Performance",
            "Resource Availability Report",
            "Critical Issues Report",
            "Custom SQL Report"
        ]
    )

    # Date range selection
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("📅 Start Date", value=datetime(2024, 12, 1))
    with col2:
        end_date = st.date_input("📅 End Date", value=datetime(2025, 6, 30))

    # County selection
    counties = st.multiselect(
        "🏛️ Select Counties:",
        ["Kisumu", "Busia", "Vihiga"],
        default=["Kisumu", "Busia", "Vihiga"]
    )

    if st.button("📊 Generate Report", type="primary", use_container_width=True):
        if not counties:
            st.error("Please select at least one county")
            return

        with st.spinner("📈 Generating comprehensive report..."):
            try:
                # Generate report based on type
                report_data = generate_report(report_type, start_date, end_date, counties)

                if report_data:
                    st.success("✅ Report generated successfully!")

                    # Display report summary
                    st.markdown("### 📋 Report Summary")

                    # Key metrics
                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        st.metric("Total CHWs", report_data.get('total_chws', 0))
                    with col2:
                        st.metric("Avg Performance", f"{report_data.get('avg_performance', 0):.1f}%")
                    with col3:
                        st.metric("Counties Covered", len(counties))
                    with col4:
                        st.metric("Data Points", report_data.get('total_records', 0))

                    # Main report data
                    if 'data' in report_data and not report_data['data'].empty:
                        st.markdown("### 📊 Detailed Results")
                        st.dataframe(report_data['data'], use_container_width=True)

                        # Export options
                        st.markdown("### 📥 Export Options")
                        col1, col2, col3 = st.columns(3)

                        with col1:
                            # CSV Export
                            csv = report_data['data'].to_csv(index=False)
                            st.download_button(
                                label="📄 Download CSV",
                                data=csv,
                                file_name=f"{report_type.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv",
                                mime="text/csv"
                            )

                        with col2:
                            # Excel Export
                            try:
                                import io
                                buffer = io.BytesIO()
                                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                                    report_data['data'].to_excel(writer, sheet_name='Report', index=False)

                                st.download_button(
                                    label="📊 Download Excel",
                                    data=buffer.getvalue(),
                                    file_name=f"{report_type.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                )
                            except ImportError:
                                st.info("Excel export requires openpyxl package")

                        with col3:
                            # PDF Report (placeholder)
                            st.button("📑 Generate PDF", disabled=True, help="PDF export coming soon")

                    # Visualizations
                    if 'charts' in report_data:
                        st.markdown("### 📈 Visualizations")
                        for chart_title, chart in report_data['charts'].items():
                            st.markdown(f"#### {chart_title}")
                            st.plotly_chart(chart, use_container_width=True)

                    # Insights and recommendations
                    if 'insights' in report_data:
                        st.markdown("### 💡 Key Insights & Recommendations")
                        for insight in report_data['insights']:
                            st.markdown(f"• {insight}")

                else:
                    st.error("❌ Could not generate report. Please check your selections.")

            except Exception as e:
                st.error(f"❌ Report generation failed: {str(e)}")
                logger.error(f"Report generation error: {e}")

    # Quick report templates
    st.markdown("---")
    st.markdown("### 🚀 Quick Report Templates")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("📊 Executive Summary", use_container_width=True):
            st.info("Generating executive summary report...")
            # Auto-generate executive summary

    with col2:
        if st.button("⚠️ Performance Alerts", use_container_width=True):
            st.info("Generating performance alerts report...")
            # Auto-generate alerts report

    with col3:
        if st.button("📈 Trend Analysis", use_container_width=True):
            st.info("Generating trend analysis report...")
            # Auto-generate trends report


def generate_report(report_type, start_date, end_date, counties):
    """Generate report data based on type and parameters"""
    try:
        engine = connect_db()
        if not engine:
            return None

        counties_str = "', '".join(counties)
        date_filter = f"reported >= '{start_date}' AND reported <= '{end_date}'"

        if report_type == "CHW Performance Summary":
            query = f"""
            SELECT
                chv_name,
                county,
                AVG(calc_assessment_score) as avg_performance,
                AVG(calc_family_planning_score) as avg_fp_score,
                AVG(calc_immunization_score) as avg_immunization_score,
                COUNT(*) as total_supervisions,
                MAX(reported) as last_supervision,
                CASE
                    WHEN AVG(calc_assessment_score) >= 85 THEN 'Excellent'
                    WHEN AVG(calc_assessment_score) >= 70 THEN 'Good'
                    WHEN AVG(calc_assessment_score) >= 50 THEN 'Needs Improvement'
                    ELSE 'Critical'
                END as performance_category
            FROM supervision
            WHERE county IN ('{counties_str}')
            AND {date_filter}
            AND calc_assessment_score IS NOT NULL
            GROUP BY chv_name, county
            ORDER BY avg_performance DESC
            """

        elif report_type == "County Comparison Report":
            query = f"""
            SELECT
                county,
                COUNT(DISTINCT chv_uuid) as total_chws,
                AVG(calc_assessment_score) as avg_performance,
                AVG(calc_family_planning_score) as avg_fp_score,
                AVG(calc_immunization_score) as avg_immunization_score,
                COUNT(CASE WHEN calc_assessment_score >= 85 THEN 1 END) as excellent_chws,
                COUNT(CASE WHEN calc_assessment_score < 50 THEN 1 END) as critical_chws,
                COUNT(*) as total_supervisions
            FROM supervision
            WHERE county IN ('{counties_str}')
            AND {date_filter}
            AND calc_assessment_score IS NOT NULL
            GROUP BY county
            ORDER BY avg_performance DESC
            """

        else:
            # Default query for other report types
            query = f"""
            SELECT
                county,
                chv_name,
                reported,
                calc_assessment_score,
                calc_family_planning_score,
                calc_immunization_score
            FROM supervision
            WHERE county IN ('{counties_str}')
            AND {date_filter}
            AND calc_assessment_score IS NOT NULL
            ORDER BY reported DESC
            LIMIT 1000
            """

        data = execute_sql_query(engine, query)

        if data is not None and not data.empty:
            # Calculate summary metrics
            total_chws = data['chv_name'].nunique() if 'chv_name' in data.columns else len(data)
            avg_performance = data['calc_assessment_score'].mean() if 'calc_assessment_score' in data.columns else 0
            total_records = len(data)

            return {
                'data': data,
                'total_chws': total_chws,
                'avg_performance': avg_performance,
                'total_records': total_records,
                'insights': [
                    f"Report covers {total_chws} CHWs across {len(counties)} counties",
                    f"Average performance score: {avg_performance:.1f}%",
                    f"Data period: {start_date} to {end_date}",
                    f"Total data points analyzed: {total_records}"
                ]
            }

        return None

    except Exception as e:
        logger.error(f"Report generation error: {e}")
        return None


def render_main_chat_interface():
    """Render the main AI chatbot interface"""
    st.markdown("## 🤖 AI Assistant - Ask Anything About Kenya Health Data")
    st.markdown("**Get instant insights, SQL queries, and analysis from your health data**")

    # Chat input
    col1, col2 = st.columns([4, 1])

    with col1:
        user_query = st.text_input(
            "Ask your question:",
            placeholder="e.g., Show me CHW performance trends in Kisumu county",
            key="chat_input"
        )

    with col2:
        send_button = st.button("🚀 Send", type="primary", use_container_width=True)

    # Quick action buttons
    st.markdown("**Quick Actions:**")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("📊 CHW Performance", use_container_width=True, key="quick_analysis_chw_perf"):
            user_query = "Show me overall CHW performance across all counties"
            send_button = True

    with col2:
        if st.button("🏥 County Comparison", use_container_width=True, key="quick_analysis_county_comp"):
            user_query = "Compare performance between Kisumu, Busia, and Vihiga counties"
            send_button = True

    with col3:
        if st.button("📈 Trends Analysis", use_container_width=True, key="quick_analysis_trends"):
            user_query = "Show me monthly performance trends for the last 6 months"
            send_button = True

    with col4:
        if st.button("⚠️ Critical Issues", use_container_width=True, key="quick_analysis_critical"):
            user_query = "Identify CHWs with critical performance scores needing intervention"
            send_button = True

    # Process query
    if (send_button and user_query) or user_query:
        if user_query.strip():
            with st.spinner("🧠 AI is analyzing your question..."):
                try:
                    # Get database connection
                    db_connection = st.session_state.get('db_connection') or connect_db()

                    # Use the AI system to process the query with RBAC
                    response = run_rbac_aware_query(user_query, db_connection)

                    if response and response.get('success'):
                        # Display the response
                        st.markdown("### 🎯 AI Analysis Results")

                        # Show SQL query if generated
                        if response.get('sql_query'):
                            with st.expander("📝 Generated SQL Query"):
                                st.code(response['sql_query'], language='sql')

                        # Show data results
                        if response.get('data') is not None and not response['data'].empty:
                            st.markdown("#### 📊 Data Results")
                            st.dataframe(response['data'], use_container_width=True)

                            # Download button for data
                            csv = response['data'].to_csv(index=False)
                            st.download_button(
                                label="📥 Download Results as CSV",
                                data=csv,
                                file_name=f"kenya_health_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv"
                            )

                        # Show AI insights
                        if response.get('analysis'):
                            st.markdown("#### 💡 AI Insights")
                            st.markdown(response['analysis'])

                        # Show visualizations if any
                        if response.get('chart'):
                            st.markdown("#### 📈 Visualization")
                            st.plotly_chart(response['chart'], use_container_width=True)

                        # Save to memory
                        save_chat_memory(user_query, response.get('analysis', 'Analysis completed'))

                    else:
                        st.error("❌ Sorry, I couldn't process your question. Please try rephrasing it.")
                        if response.get('error'):
                            st.error(f"Error details: {response['error']}")

                except Exception as e:
                    st.error(f"❌ An error occurred: {str(e)}")
                    logger.error(f"Chat interface error: {e}")

    # Chat history
    st.markdown("---")
    st.markdown("### 📚 Recent Conversations")

    chat_history = load_chat_memory()
    if chat_history:
        for i, (query, response) in enumerate(reversed(chat_history[-5:])):
            with st.expander(f"💬 {query[:80]}..."):
                st.markdown(f"**Question:** {query}")
                st.markdown(f"**Response:** {response[:500]}...")
                if st.button(f"🔄 Ask Again", key=f"repeat_{i}"):
                    st.session_state.chat_input = query
                    st.rerun()
    else:
        st.info("💡 No conversation history yet. Start by asking a question above!")


def render_reports_tab():
    """Render comprehensive reports and analytics"""
    st.markdown("## 📊 Reports & Analytics Dashboard")
    st.markdown("**Generate comprehensive reports and export data for stakeholders**")

    # Report type selection
    report_type = st.selectbox(
        "📋 Select Report Type:",
        [
            "CHW Performance Summary",
            "County Comparison Report",
            "Monthly Trends Analysis",
            "Service Area Performance",
            "Resource Availability Report",
            "Critical Issues Report",
            "Custom SQL Report"
        ]
    )

    # Date range selection
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("📅 Start Date", value=datetime(2024, 12, 1))
    with col2:
        end_date = st.date_input("📅 End Date", value=datetime(2025, 6, 30))

    # County selection
    counties = st.multiselect(
        "🏛️ Select Counties:",
        ["Kisumu", "Busia", "Vihiga"],
        default=["Kisumu", "Busia", "Vihiga"]
    )

    if st.button("📊 Generate Report", type="primary", use_container_width=True):
        if not counties:
            st.error("Please select at least one county")
            return

        with st.spinner("📈 Generating comprehensive report..."):
            try:
                # Generate report based on type
                report_data = generate_report(report_type, start_date, end_date, counties)

                if report_data:
                    st.success("✅ Report generated successfully!")

                    # Display report summary
                    st.markdown("### 📋 Report Summary")

                    # Key metrics
                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        st.metric("Total CHWs", report_data.get('total_chws', 0))
                    with col2:
                        st.metric("Avg Performance", f"{report_data.get('avg_performance', 0):.1f}%")
                    with col3:
                        st.metric("Counties Covered", len(counties))
                    with col4:
                        st.metric("Data Points", report_data.get('total_records', 0))

                    # Main report data
                    if 'data' in report_data and not report_data['data'].empty:
                        st.markdown("### 📊 Detailed Results")
                        st.dataframe(report_data['data'], use_container_width=True)

                        # Export options
                        st.markdown("### 📥 Export Options")
                        col1, col2, col3 = st.columns(3)

                        with col1:
                            # CSV Export
                            csv = report_data['data'].to_csv(index=False)
                            st.download_button(
                                label="📄 Download CSV",
                                data=csv,
                                file_name=f"{report_type.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv",
                                mime="text/csv"
                            )

                        with col2:
                            # Excel Export
                            try:
                                import io
                                buffer = io.BytesIO()
                                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                                    report_data['data'].to_excel(writer, sheet_name='Report', index=False)

                                st.download_button(
                                    label="📊 Download Excel",
                                    data=buffer.getvalue(),
                                    file_name=f"{report_type.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                )
                            except ImportError:
                                st.info("Excel export requires openpyxl package")

                        with col3:
                            # PDF Report (placeholder)
                            st.button("📑 Generate PDF", disabled=True, help="PDF export coming soon")

                    # Insights and recommendations
                    if 'insights' in report_data:
                        st.markdown("### 💡 Key Insights & Recommendations")
                        for insight in report_data['insights']:
                            st.markdown(f"• {insight}")

                else:
                    st.error("❌ Could not generate report. Please check your selections.")

            except Exception as e:
                st.error(f"❌ Report generation failed: {str(e)}")
                logger.error(f"Report generation error: {e}")


def generate_report(report_type, start_date, end_date, counties):
    """Generate report data based on type and parameters"""
    try:
        engine = connect_db()
        if not engine:
            return None

        counties_str = "', '".join(counties)
        date_filter = f"reported >= '{start_date}' AND reported <= '{end_date}'"

        if report_type == "CHW Performance Summary":
            query = f"""
            SELECT
                chv_name,
                county,
                AVG(calc_assessment_score) as avg_performance,
                AVG(calc_family_planning_score) as avg_fp_score,
                AVG(calc_immunization_score) as avg_immunization_score,
                COUNT(*) as total_supervisions,
                MAX(reported) as last_supervision,
                CASE
                    WHEN AVG(calc_assessment_score) >= 85 THEN 'Excellent'
                    WHEN AVG(calc_assessment_score) >= 70 THEN 'Good'
                    WHEN AVG(calc_assessment_score) >= 50 THEN 'Needs Improvement'
                    ELSE 'Critical'
                END as performance_category
            FROM supervision
            WHERE county IN ('{counties_str}')
            AND {date_filter}
            AND calc_assessment_score IS NOT NULL
            GROUP BY chv_name, county
            ORDER BY avg_performance DESC
            """

        elif report_type == "County Comparison Report":
            query = f"""
            SELECT
                county,
                COUNT(DISTINCT chv_uuid) as total_chws,
                AVG(calc_assessment_score) as avg_performance,
                AVG(calc_family_planning_score) as avg_fp_score,
                AVG(calc_immunization_score) as avg_immunization_score,
                COUNT(CASE WHEN calc_assessment_score >= 85 THEN 1 END) as excellent_chws,
                COUNT(CASE WHEN calc_assessment_score < 50 THEN 1 END) as critical_chws,
                COUNT(*) as total_supervisions
            FROM supervision
            WHERE county IN ('{counties_str}')
            AND {date_filter}
            AND calc_assessment_score IS NOT NULL
            GROUP BY county
            ORDER BY avg_performance DESC
            """

        else:
            # Default query for other report types
            query = f"""
            SELECT
                county,
                chv_name,
                reported,
                calc_assessment_score,
                calc_family_planning_score,
                calc_immunization_score
            FROM supervision
            WHERE county IN ('{counties_str}')
            AND {date_filter}
            AND calc_assessment_score IS NOT NULL
            ORDER BY reported DESC
            LIMIT 1000
            """

        data = execute_sql_query(engine, query)

        if data is not None and not data.empty:
            # Calculate summary metrics
            total_chws = data['chv_name'].nunique() if 'chv_name' in data.columns else len(data)
            avg_performance = data['calc_assessment_score'].mean() if 'calc_assessment_score' in data.columns else 0
            total_records = len(data)

            return {
                'data': data,
                'total_chws': total_chws,
                'avg_performance': avg_performance,
                'total_records': total_records,
                'insights': [
                    f"Report covers {total_chws} CHWs across {len(counties)} counties",
                    f"Average performance score: {avg_performance:.1f}%",
                    f"Data period: {start_date} to {end_date}",
                    f"Total data points analyzed: {total_records}"
                ]
            }

        return None

    except Exception as e:
        logger.error(f"Report generation error: {e}")
        return None


def render_predefined_queries_tab():
    """Render predefined queries tab with organized categories"""
    st.markdown("## 🔍 Quick Analysis Templates")
    st.markdown("**Click any button below to run pre-built analysis queries**")

    # Create tabs for different query categories
    query_tab1, query_tab2, query_tab3, query_tab4 = st.tabs([
        "📊 Performance", "📈 Trends", "🧰 Resources", "🏥 Services"
    ])

    with query_tab1:
        st.markdown("### 📊 Performance Analysis")
        col1, col2 = st.columns(2)

        with col1:
            if st.button("🏆 Top Performing CHWs", use_container_width=True):
                run_predefined_query("Show me the top 10 performing CHWs across all counties")

            if st.button("⚠️ CHWs Needing Support", use_container_width=True):
                run_predefined_query("Identify CHWs with performance scores below 50% who need immediate intervention")

            if st.button("📊 County Performance Ranking", use_container_width=True):
                run_predefined_query("Rank counties by overall CHW performance")

        with col2:
            if st.button("🎯 Family Planning Leaders", use_container_width=True):
                run_predefined_query("Show CHWs with highest family planning scores in each county")

            if st.button("💉 Immunization Champions", use_container_width=True):
                run_predefined_query("Identify top immunization performers by county")

            if st.button("📈 Performance Distribution", use_container_width=True):
                run_predefined_query("Show distribution of performance scores across all CHWs")

    with query_tab2:
        st.markdown("### 📈 Trend Analysis")
        col1, col2 = st.columns(2)

        with col1:
            if st.button("📅 Monthly Trends", use_container_width=True):
                run_predefined_query("Show monthly performance trends for the last 6 months")

            if st.button("🔄 Quarterly Comparison", use_container_width=True):
                run_predefined_query("Compare quarterly performance across counties")

            if st.button("📊 Service Area Trends", use_container_width=True):
                run_predefined_query("Analyze trends in family planning and immunization services")

        with col2:
            if st.button("⬆️ Improving CHWs", use_container_width=True):
                run_predefined_query("Identify CHWs showing improvement over time")

            if st.button("⬇️ Declining Performance", use_container_width=True):
                run_predefined_query("Find CHWs with declining performance trends")

            if st.button("🎯 Supervision Impact", use_container_width=True):
                run_predefined_query("Analyze impact of supervision frequency on performance")

    with query_tab3:
        st.markdown("### 🧰 Resource Analysis")
        col1, col2 = st.columns(2)

        with col1:
            if st.button("🧰 Tool Availability", use_container_width=True):
                run_predefined_query("Show tool and equipment availability by county")

            if st.button("💊 Medicine Stock Status", use_container_width=True):
                run_predefined_query("Analyze medicine stock levels across counties")

            if st.button("🦺 PPE Availability", use_container_width=True):
                run_predefined_query("Check PPE availability and gaps")

        with col2:
            if st.button("📚 Training Needs", use_container_width=True):
                run_predefined_query("Identify CHWs needing additional training")

            if st.button("🚨 Resource Gaps", use_container_width=True):
                run_predefined_query("Identify critical resource shortages by area")

            if st.button("📊 Resource Utilization", use_container_width=True):
                run_predefined_query("Analyze resource utilization efficiency")

    with query_tab4:
        st.markdown("### 🏥 Service Analysis")
        col1, col2 = st.columns(2)

        with col1:
            if st.button("👶 Newborn Care Services", use_container_width=True):
                run_predefined_query("Analyze newborn care service delivery")

            if st.button("🍎 Nutrition Programs", use_container_width=True):
                run_predefined_query("Show nutrition program performance")

            if st.button("🏥 Service Coverage", use_container_width=True):
                run_predefined_query("Analyze service coverage by geographic area")

        with col2:
            if st.button("👥 Community Engagement", use_container_width=True):
                run_predefined_query("Measure community engagement levels")

            if st.button("📋 Service Quality", use_container_width=True):
                run_predefined_query("Assess service quality indicators")

            if st.button("🎯 Target Achievement", use_container_width=True):
                run_predefined_query("Track progress toward health targets")


def run_predefined_query(query):
    """Run a predefined query and display results"""
    with st.spinner(f"🧠 Running analysis: {query[:50]}..."):
        try:
            # Get database connection
            db_connection = st.session_state.get('db_connection') or connect_db()

            # Run the group chat with proper arguments and RBAC
            response = run_rbac_aware_query(query, db_connection)

            if response and response.get('success'):
                st.success("✅ Analysis completed!")

                # Show results
                if response.get('data') is not None and not response['data'].empty:
                    st.markdown("#### 📊 Results")
                    st.dataframe(response['data'], use_container_width=True)

                    # Download button
                    csv = response['data'].to_csv(index=False)
                    st.download_button(
                        label="📥 Download Results",
                        data=csv,
                        file_name=f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )

                if response.get('analysis'):
                    st.markdown("#### 💡 Insights")
                    st.markdown(response['analysis'])

                if response.get('chart'):
                    st.markdown("#### 📈 Visualization")
                    st.plotly_chart(response['chart'], use_container_width=True)
            else:
                st.error("❌ Analysis failed. Please try again.")

        except Exception as e:
            st.error(f"❌ Error running analysis: {str(e)}")


def render_sample_queries():
    """Render organized sample queries by category"""
    st.subheader("💡 Sample Questions You Can Ask")
    
    # Create tabs for different query categories
    tab1, tab2, tab3, tab4 = st.tabs(["🎯 Performance", "📈 Trends", "🧰 Resources", "💊 Services"])
    
    with tab1:
        st.write("**Performance Analysis Queries:**")
        for query in SAMPLE_QUERIES["Performance Analysis"]:
            if st.button(f"📊 {query}", key=f"perf_{hash(query)}", use_container_width=True):
                st.session_state.suggested_query = query
                st.rerun()
    
    with tab2:
        st.write("**Trend Analysis Queries:**")
        for query in SAMPLE_QUERIES["Trend Analysis"]:
            if st.button(f"📈 {query}", key=f"trend_{hash(query)}", use_container_width=True):
                st.session_state.suggested_query = query
                st.rerun()
    
    with tab3:
        st.write("**Resource & Training Queries:**")
        for query in SAMPLE_QUERIES["Resource & Training"]:
            if st.button(f"🧰 {query}", key=f"resource_{hash(query)}", use_container_width=True):
                st.session_state.suggested_query = query
                st.rerun()
    
    with tab4:
        st.write("**Service Delivery Queries:**")
        for query in SAMPLE_QUERIES["Service Delivery"]:
            if st.button(f"💊 {query}", key=f"service_{hash(query)}", use_container_width=True):
                st.session_state.suggested_query = query
                st.rerun()

def show_performance_monitor_page():
    """Show performance monitoring page"""
    st.title("📊 Performance Monitoring Dashboard")

    if st.button("← Back to Main", key="back_from_perf"):
        if 'page' in st.session_state:
            del st.session_state.page
        st.rerun()

    st.markdown("---")

    # Embed the monitoring dashboard
    st.markdown("""
    **Performance Monitoring Dashboard**

    To access the full interactive performance monitoring dashboard, run:
    ```bash
    python run_monitoring_dashboard.py
    ```

    Or visit: http://localhost:8503
    """)

    # Show basic performance stats
    try:
        from monitoring.performance_monitor import get_performance_summary
        performance_data = get_performance_summary()

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Health Score", f"{performance_data.get('health_score', 0):.1f}/100")

        with col2:
            st.metric("System Status", performance_data.get('system_status', 'unknown').title())

        with col3:
            session_data = performance_data.get('metrics', {}).get('session', {})
            st.metric("Success Rate", f"{session_data.get('success_rate', 0):.1f}%")

        with col4:
            st.metric("Avg Response Time", f"{session_data.get('avg_response_time', 0):.2f}s")

    except Exception as e:
        st.error(f"Error loading performance data: {e}")

def show_cache_management_page():
    """Show cache management page"""
    st.title("🔄 Cache Management")

    if st.button("← Back to Main", key="back_from_cache"):
        if 'page' in st.session_state:
            del st.session_state.page
        st.rerun()

    st.markdown("---")

    # Cache statistics
    try:
        from caching.enhanced_cache import get_cache_statistics
        cache_stats = get_cache_statistics()

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Entries", cache_stats.get('total_entries', 0))

        with col2:
            st.metric("Memory Usage", f"{cache_stats.get('total_size_mb', 0)} MB")

        with col3:
            st.metric("Hit Rate", f"{cache_stats.get('hit_rate_percent', 0):.1f}%")

        with col4:
            st.metric("Cache Types", len(cache_stats.get('type_breakdown', {})))

        # Cache actions
        st.subheader("🔧 Cache Actions")

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("🧹 Clear Expired", use_container_width=True, key="cache_clear_expired"):
                from caching.enhanced_cache import get_enhanced_cache
                cache = get_enhanced_cache()
                cleared = cache.clear_expired()
                st.success(f"Cleared {cleared} expired entries")
                st.rerun()

        with col2:
            if st.button("📊 View Stats", use_container_width=True, key="cache_view_stats"):
                st.json(cache_stats)

        with col3:
            if st.button("🔄 Refresh", use_container_width=True, key="cache_refresh"):
                st.rerun()

    except Exception as e:
        st.error(f"Error loading cache data: {e}")


@protected_page(title="🏥 Ushauri AI - Kenya Community Health Systems")
def main():
    """Main application function with enhanced navigation and error handling"""

    try:
        # Initialize RBAC system if enabled
        if RBAC_ENABLED:
            init_auth_system()

            # Check if user is authenticated
            if not is_authenticated():
                show_login_page()
                return

        # Initialize application
        initialize_app()
        
        # Render header
        render_header()
        
        # Render sidebar
        render_sidebar()

        # Check for RBAC page routing
        if RBAC_ENABLED and 'page' in st.session_state:
            if st.session_state.page == "user_management":
                show_user_management()
                return
            elif st.session_state.page == "performance_monitor":
                show_performance_monitor_page()
                return
            elif st.session_state.page == "cache_management":
                show_cache_management_page()
                return

        # Main content with enhanced tabs
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "🏠 Dashboard",
            "💬 AI Assistant",
            "📋 Quick Analysis",
            "📊 Reports & Analytics",
            "🔍 Sample Queries"
        ])
        
        with tab1:
            st.markdown("## 📊 Ushauri AI - Kenya Community Health Systems")
            st.markdown("**Real-time insights from Kisumu, Busia, and Vihiga counties**")
            
            # Enhanced dashboard metrics
            render_enhanced_dashboard_metrics()
            
            # System-wide insights
            st.markdown("### 💡 Key Insights")
            
            if st.session_state.db_connection:
                try:
                    # Quick insight generation
                    insight_query = """
                    SELECT 
                        COUNT(CASE WHEN calc_assessment_score >= 85 THEN 1 END) as excellent_chws,
                        COUNT(CASE WHEN calc_assessment_score < 50 THEN 1 END) as critical_chws,
                        AVG(calc_family_planning_score) as avg_fp_score,
                        COUNT(CASE WHEN has_all_tools = 'yes' THEN 1 END) as chws_with_tools,
                        COUNT(*) as total_assessments
                    FROM supervision 
                    WHERE county IN ('Kisumu', 'Busia', 'Vihiga')
                    AND reported >= '2024-12-01' AND reported <= '2025-06-30'
                    AND calc_assessment_score IS NOT NULL
                    """
                    
                    insights = execute_sql_query(st.session_state.db_connection, insight_query)
                    
                    if insights is not None and not insights.empty:
                        insight_data = insights.iloc[0]
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown(f"""
                            <div class="insight-box">
                                <h4>🌟 System Highlights</h4>
                                <ul>
                                    <li><strong>{insight_data['excellent_chws']}</strong> CHWs performing excellently (≥85%)</li>
                                    <li><strong>{insight_data['avg_fp_score']:.1f}%</strong> average family planning score</li>
                                    <li><strong>{insight_data['chws_with_tools']}</strong> CHWs have all required tools</li>
                                </ul>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        with col2:
                            if insight_data['critical_chws'] > 0:
                                st.markdown(f"""
                                <div class="alert-critical">
                                    <h4>⚠️ Areas Needing Attention</h4>
                                    <ul>
                                        <li><strong>{insight_data['critical_chws']}</strong> CHWs require immediate intervention</li>
                                        <li>Focus on performance improvement programs</li>
                                        <li>Consider additional training and support</li>
                                    </ul>
                                </div>
                                """, unsafe_allow_html=True)
                            else:
                                st.markdown("""
                                <div class="insight-box">
                                    <h4>✅ System Performance</h4>
                                    <p>All CHWs performing above critical threshold!</p>
                                    <p>Continue current support and monitoring.</p>
                                </div>
                                """, unsafe_allow_html=True)
                
                except Exception as e:
                    st.error(f"❌ Could not generate insights: {e}")
            
            # Recent activity section
            st.markdown("### 🕒 Recent Analysis Activity")
            chat_history = load_chat_memory()
            
            if chat_history:
                for i, (query, response) in enumerate(chat_history[-3:]):
                    with st.expander(f"Q{len(chat_history)-2+i}: {query[:60]}..."):
                        st.markdown(f"**Question:** {query}")
                        st.markdown(f"**Analysis:** {response[:300]}...")
                        if st.button(f"🔄 Re-run Analysis", key=f"rerun_{i}"):
                            st.session_state.user_query_input = query
                            st.switch_page("💬 AI Assistant")
            else:
                st.info("💡 No recent activity. Start by asking a question in the AI Assistant tab!")
        
        with tab2:
            render_main_chat_interface()
        
        with tab3:
            render_predefined_queries_tab()
        
        with tab4:
            render_reports_tab()
        
        with tab5:
            render_sample_queries()
        
        # Enhanced footer with system information
        st.markdown("---")
        st.markdown("""
        <div style="text-align: center; color: #666; margin-top: 2rem;">
            <h4>🇰🇪 <strong>Ushauri AI</strong> - Kenya Health Intelligence System</h4>
            <p><strong>Specialized for:</strong> Kisumu, Busia & Vihiga Counties | December 2024 - June 2025</p>
            <p><strong>Powered by:</strong> Microsoft AutoGen • PostgreSQL • Streamlit • Hugging Face AI</p>
            <p><strong>Built for:</strong> M&E Officers • Health Supervisors • County Health Management Teams</p>
            <div style="margin-top: 1rem;">
                <span style="background: #e3f2fd; padding: 0.25rem 0.5rem; border-radius: 15px; margin: 0 0.25rem; font-size: 0.8rem;">
                    🎯 150+ CHWs Monitored
                </span>
                <span style="background: #f3e5f5; padding: 0.25rem 0.5rem; border-radius: 15px; margin: 0 0.25rem; font-size: 0.8rem;">
                    📊 Real-time Analytics
                </span>
                <span style="background: #e8f5e8; padding: 0.25rem 0.5rem; border-radius: 15px; margin: 0 0.25rem; font-size: 0.8rem;">
                    🤖 AI-Powered Insights
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    except Exception as e:
        st.error(f"❌ Application error: {e}")
        logger.error(f"Application error: {e}")
        
        # Error recovery options
        st.markdown("### 🔧 Error Recovery Options")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🔄 Refresh Page", use_container_width=True):
                st.rerun()
        
        with col2:
            if st.button("🧹 Clear Session", use_container_width=True):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
        
        with col3:
            if st.button("🔍 Show Error Details", use_container_width=True):
                st.exception(e)
        
        # Provide alternative access
        st.markdown("### 📞 Support Information")
        st.markdown("""
        If the error persists:
        1. **Refresh** the page and try again
        2. **Check** your internet connection
        3. **Contact** the system administrator
        4. **Report** the issue with error details
        
        **System Status:** Check database connectivity and AI service availability.
        """)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"❌ Critical application error: {e}")
        logger.error(f"Critical application error: {e}")
        
        # Emergency fallback interface
        st.markdown("## ⚠️ System Recovery Mode")
        st.markdown("The application encountered a critical error. Please contact support.")
        
        if st.button("🆘 Emergency Reset"):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.rerun()
