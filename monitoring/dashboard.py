"""
Real-time Performance Monitoring Dashboard for Ushauri AI
Kenya Community Health Systems - Streamlit-based dashboard for system monitoring and alerting
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime, timedelta
import time
import json
from pathlib import Path
import sys

# Add parent directory to path to import monitoring modules
sys.path.append(str(Path(__file__).parent.parent))

from monitoring.performance_monitor import performance_monitor, get_performance_summary

# Page configuration
st.set_page_config(
    page_title="Ushauri AI - Performance Monitor",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

def main():
    """Main dashboard application"""
    
    # Header
    st.title("🏥 Ushauri AI - Performance Monitor")
    st.markdown("Kenya Community Health Systems - Real-time performance monitoring and alerting")
    
    # Sidebar controls
    st.sidebar.header("⚙️ Dashboard Controls")
    
    # Auto-refresh toggle
    auto_refresh = st.sidebar.checkbox("Auto-refresh (30s)", value=True)
    
    # Manual refresh button
    if st.sidebar.button("🔄 Refresh Now"):
        st.rerun()
    
    # Reset session metrics button
    if st.sidebar.button("🔄 Reset Session Metrics"):
        performance_monitor.reset_session_metrics()
        st.sidebar.success("Session metrics reset!")
        time.sleep(1)
        st.rerun()
    
    # Get current performance data
    try:
        performance_data = get_performance_summary()
    except Exception as e:
        st.error(f"Error loading performance data: {e}")
        return
    
    # System Health Overview
    display_system_health(performance_data)
    
    # Metrics Dashboard
    display_metrics_dashboard(performance_data)
    
    # Recent Alerts
    display_alerts_section(performance_data)
    
    # Performance Trends
    display_performance_trends(performance_data)
    
    # System Information
    display_system_info(performance_data)
    
    # Auto-refresh
    if auto_refresh:
        time.sleep(30)
        st.rerun()

def display_system_health(performance_data):
    """Display system health overview"""
    st.header("🎯 System Health Overview")
    
    health_score = performance_data.get('health_score', 0)
    system_status = performance_data.get('system_status', 'unknown')
    
    # Create columns for health metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # Health score gauge
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number+delta",
            value = health_score,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "Health Score"},
            delta = {'reference': 90},
            gauge = {
                'axis': {'range': [None, 100]},
                'bar': {'color': get_health_color(health_score)},
                'steps': [
                    {'range': [0, 40], 'color': "lightgray"},
                    {'range': [40, 75], 'color': "yellow"},
                    {'range': [75, 90], 'color': "lightgreen"},
                    {'range': [90, 100], 'color': "green"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 90
                }
            }
        ))
        fig_gauge.update_layout(height=200, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig_gauge, use_container_width=True)
    
    with col2:
        st.metric(
            label="System Status",
            value=system_status.title(),
            delta=None
        )
        
        # Session metrics
        session_data = performance_data.get('metrics', {}).get('session', {})
        st.metric(
            label="Success Rate",
            value=f"{session_data.get('success_rate', 0):.1f}%",
            delta=f"{session_data.get('success_rate', 0) - 95:.1f}%" if session_data.get('success_rate', 0) < 95 else None
        )
    
    with col3:
        st.metric(
            label="Total Requests",
            value=session_data.get('total_requests', 0),
            delta=None
        )
        
        st.metric(
            label="Avg Response Time",
            value=f"{session_data.get('avg_response_time', 0):.2f}s",
            delta=f"{session_data.get('avg_response_time', 0) - 10:.2f}s" if session_data.get('avg_response_time', 0) > 10 else None
        )
    
    with col4:
        st.metric(
            label="Uptime",
            value=f"{session_data.get('uptime_minutes', 0):.1f} min",
            delta=None
        )
        
        # Recent alerts count
        recent_alerts = performance_data.get('recent_alerts', [])
        critical_alerts = sum(1 for alert in recent_alerts if alert.get('severity') == 'critical')
        st.metric(
            label="Critical Alerts",
            value=critical_alerts,
            delta=f"+{critical_alerts}" if critical_alerts > 0 else None
        )

def display_metrics_dashboard(performance_data):
    """Display key performance metrics"""
    st.header("📊 Performance Metrics")
    
    metrics = performance_data.get('metrics', {})
    
    # Create columns for different metric categories
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("⚡ Execution Times")
        
        # Workflow execution time
        if 'workflow_execution_time' in metrics:
            workflow_data = metrics['workflow_execution_time']
            st.metric(
                label="Workflow Execution Time",
                value=f"{workflow_data.get('current', 0):.2f}s",
                delta=f"{workflow_data.get('current', 0) - workflow_data.get('average_10', 0):.2f}s"
            )
        
        # SQL generation time
        if 'sql_generation_time' in metrics:
            sql_data = metrics['sql_generation_time']
            st.metric(
                label="SQL Generation Time",
                value=f"{sql_data.get('current', 0):.2f}s",
                delta=f"{sql_data.get('current', 0) - sql_data.get('average_10', 0):.2f}s"
            )
        
        # Analysis time
        if 'analysis_time' in metrics:
            analysis_data = metrics['analysis_time']
            st.metric(
                label="Analysis Time",
                value=f"{analysis_data.get('current', 0):.2f}s",
                delta=f"{analysis_data.get('current', 0) - analysis_data.get('average_10', 0):.2f}s"
            )
    
    with col2:
        st.subheader("🌐 API & Database")
        
        # API response time
        if 'api_response_time' in metrics:
            api_data = metrics['api_response_time']
            st.metric(
                label="API Response Time",
                value=f"{api_data.get('current', 0):.2f}s",
                delta=f"{api_data.get('current', 0) - api_data.get('average_10', 0):.2f}s"
            )
        
        # Database query time
        if 'database_query_time' in metrics:
            db_data = metrics['database_query_time']
            st.metric(
                label="Database Query Time",
                value=f"{db_data.get('current', 0):.2f}s",
                delta=f"{db_data.get('current', 0) - db_data.get('average_10', 0):.2f}s"
            )

def display_alerts_section(performance_data):
    """Display recent alerts"""
    st.header("🚨 Recent Alerts")
    
    recent_alerts = performance_data.get('recent_alerts', [])
    
    if not recent_alerts:
        st.success("✅ No recent alerts - system running smoothly!")
        return
    
    # Create alerts dataframe
    alerts_df = pd.DataFrame(recent_alerts)
    
    # Display alerts by severity
    for severity in ['critical', 'warning', 'info']:
        severity_alerts = [alert for alert in recent_alerts if alert.get('severity') == severity]
        
        if severity_alerts:
            if severity == 'critical':
                st.error(f"🔴 Critical Alerts ({len(severity_alerts)})")
            elif severity == 'warning':
                st.warning(f"🟡 Warning Alerts ({len(severity_alerts)})")
            else:
                st.info(f"🔵 Info Alerts ({len(severity_alerts)})")
            
            for alert in severity_alerts[-3:]:  # Show last 3 alerts per severity
                with st.expander(f"{alert.get('metric_name', 'Unknown')} - {alert.get('message', '')[:50]}..."):
                    st.write(f"**Time:** {alert.get('timestamp', '')}")
                    st.write(f"**Metric:** {alert.get('metric_name', '')}")
                    st.write(f"**Message:** {alert.get('message', '')}")
                    st.write(f"**Current Value:** {alert.get('current_value', 0)}")
                    st.write(f"**Threshold:** {alert.get('threshold', 0)}")

def display_performance_trends(performance_data):
    """Display performance trends charts"""
    st.header("📈 Performance Trends")
    
    # Note: In a real implementation, you would store historical data
    # For now, we'll show current metrics in a simple format
    
    metrics = performance_data.get('metrics', {})
    
    if not metrics:
        st.info("No performance data available yet. Run some queries to see trends.")
        return
    
    # Create a simple bar chart of current metrics
    metric_names = []
    current_values = []
    average_values = []
    
    for metric_name, metric_data in metrics.items():
        if metric_name != 'session' and isinstance(metric_data, dict):
            metric_names.append(metric_name.replace('_', ' ').title())
            current_values.append(metric_data.get('current', 0))
            average_values.append(metric_data.get('average_10', 0))
    
    if metric_names:
        fig = go.Figure(data=[
            go.Bar(name='Current', x=metric_names, y=current_values),
            go.Bar(name='Average (Last 10)', x=metric_names, y=average_values)
        ])
        
        fig.update_layout(
            title="Current vs Average Performance Metrics",
            xaxis_title="Metrics",
            yaxis_title="Time (seconds)",
            barmode='group',
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)

def display_system_info(performance_data):
    """Display system information and thresholds"""
    st.header("ℹ️ System Information")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Performance Thresholds")
        thresholds = performance_data.get('thresholds', {})
        
        for metric_name, threshold_data in thresholds.items():
            with st.expander(f"{metric_name.replace('_', ' ').title()}"):
                if 'warning' in threshold_data:
                    st.write(f"⚠️ Warning: {threshold_data['warning']}")
                if 'critical' in threshold_data:
                    st.write(f"🔴 Critical: {threshold_data['critical']}")
    
    with col2:
        st.subheader("System Status")
        st.write(f"**Last Updated:** {performance_data.get('timestamp', 'Unknown')}")
        st.write(f"**Health Score:** {performance_data.get('health_score', 0):.1f}/100")
        st.write(f"**System Status:** {performance_data.get('system_status', 'Unknown').title()}")
        
        # Export data button
        if st.button("📥 Export Performance Data"):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"performance_data_{timestamp}.json"
            
            with open(filename, 'w') as f:
                json.dump(performance_data, f, indent=2, default=str)
            
            st.success(f"Performance data exported to {filename}")

def get_health_color(health_score):
    """Get color based on health score"""
    if health_score >= 90:
        return "green"
    elif health_score >= 75:
        return "lightgreen"
    elif health_score >= 60:
        return "yellow"
    elif health_score >= 40:
        return "orange"
    else:
        return "red"

if __name__ == "__main__":
    main()
