#!/usr/bin/env python3
"""
Test script to verify performance monitoring is working
"""

import sys
import json
from pathlib import Path

# Add current directory to path
sys.path.append(str(Path(__file__).parent))

from monitoring.performance_monitor import get_performance_summary, record_performance_metric
import time

def test_performance_monitoring():
    """Test the performance monitoring system"""
    
    print("🧪 Testing Performance Monitoring System...")
    print("-" * 50)
    
    # Record some test metrics
    print("📊 Recording test metrics...")
    
    # Simulate some workflow metrics
    record_performance_metric('workflow_execution_time', 2.82, 'seconds', {
        'user_question_length': 35,
        'has_data': True,
        'data_rows': 1,
        'analysis_type': 'general_query'
    })
    
    record_performance_metric('sql_generation_time', 1.52, 'seconds', {
        'query_length': 35,
        'sql_length': 72
    })
    
    record_performance_metric('database_query_time', 0.010, 'seconds', {
        'query_length': 72,
        'result_rows': 1,
        'result_columns': 1
    })
    
    record_performance_metric('analysis_time', 4.23, 'seconds', {
        'data_rows': 1,
        'data_columns': 1,
        'analysis_type': 'general_query'
    })
    
    # Add some test metrics that should trigger alerts
    print("⚠️  Recording metrics that should trigger alerts...")
    
    # This should trigger a warning (>8s)
    record_performance_metric('workflow_execution_time', 9.5, 'seconds', {
        'user_question_length': 50,
        'has_data': False
    })
    
    # This should trigger a critical alert (>15s)
    record_performance_metric('workflow_execution_time', 16.2, 'seconds', {
        'user_question_length': 100,
        'has_data': False
    })
    
    print("✅ Test metrics recorded successfully!")
    print()
    
    # Get performance summary
    print("📈 Getting performance summary...")
    summary = get_performance_summary()
    
    print(f"🎯 System Health Score: {summary['health_score']:.1f}/100")
    print(f"📊 System Status: {summary['system_status'].title()}")
    print()
    
    # Display key metrics
    metrics = summary.get('metrics', {})
    if 'workflow_execution_time' in metrics:
        workflow_data = metrics['workflow_execution_time']
        print(f"⚡ Workflow Execution Time:")
        print(f"   Current: {workflow_data.get('current', 0):.2f}s")
        print(f"   Average (last 10): {workflow_data.get('average_10', 0):.2f}s")
        print(f"   Min: {workflow_data.get('min_10', 0):.2f}s")
        print(f"   Max: {workflow_data.get('max_10', 0):.2f}s")
        print()
    
    # Display recent alerts
    recent_alerts = summary.get('recent_alerts', [])
    if recent_alerts:
        print(f"🚨 Recent Alerts ({len(recent_alerts)}):")
        for alert in recent_alerts[-3:]:  # Show last 3 alerts
            severity_emoji = {
                'critical': '🔴',
                'warning': '🟡',
                'info': '🔵'
            }.get(alert.get('severity', 'info'), '🔵')
            
            print(f"   {severity_emoji} {alert.get('severity', 'info').upper()}: {alert.get('message', '')}")
        print()
    else:
        print("✅ No alerts - system running smoothly!")
        print()
    
    # Session metrics
    session_data = metrics.get('session', {})
    if session_data:
        print(f"📊 Session Metrics:")
        print(f"   Total Requests: {session_data.get('total_requests', 0)}")
        print(f"   Success Rate: {session_data.get('success_rate', 0):.1f}%")
        print(f"   Avg Response Time: {session_data.get('avg_response_time', 0):.2f}s")
        print(f"   Uptime: {session_data.get('uptime_minutes', 0):.1f} minutes")
        print()
    
    # Save summary to file
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_file = f"performance_test_summary_{timestamp}.json"
    
    with open(output_file, 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    
    print(f"💾 Performance summary saved to: {output_file}")
    print()
    
    # Test dashboard launch instructions
    print("🌐 To view the monitoring dashboard:")
    print("   python run_monitoring_dashboard.py")
    print("   or")
    print("   streamlit run monitoring/dashboard.py --server.port 8503")
    print()
    
    print("✅ Performance monitoring test completed successfully!")
    
    return summary

if __name__ == "__main__":
    try:
        summary = test_performance_monitoring()
        
        # Return appropriate exit code based on system health
        health_score = summary.get('health_score', 0)
        if health_score >= 90:
            print("🎉 System health: EXCELLENT")
            exit(0)
        elif health_score >= 75:
            print("👍 System health: GOOD")
            exit(0)
        elif health_score >= 60:
            print("⚠️  System health: FAIR")
            exit(1)
        else:
            print("🚨 System health: POOR - Needs attention!")
            exit(2)
            
    except Exception as e:
        print(f"❌ Error testing performance monitoring: {e}")
        exit(3)
