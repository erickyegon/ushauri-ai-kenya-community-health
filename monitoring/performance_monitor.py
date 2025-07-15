"""
Performance Monitoring System for Kenya Health AI
Real-time metrics tracking, alerting, and dashboard
"""

import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import threading
import os
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetric:
    """Individual performance metric data point"""
    timestamp: datetime
    metric_name: str
    value: float
    unit: str
    metadata: Dict[str, Any] = None
    
    def to_dict(self):
        return {
            'timestamp': self.timestamp.isoformat(),
            'metric_name': self.metric_name,
            'value': self.value,
            'unit': self.unit,
            'metadata': self.metadata or {}
        }

@dataclass
class SystemAlert:
    """System performance alert"""
    timestamp: datetime
    alert_type: str
    severity: str  # 'low', 'medium', 'high', 'critical'
    message: str
    metric_name: str
    current_value: float
    threshold: float
    
    def to_dict(self):
        return {
            'timestamp': self.timestamp.isoformat(),
            'alert_type': self.alert_type,
            'severity': self.severity,
            'message': self.message,
            'metric_name': self.metric_name,
            'current_value': self.current_value,
            'threshold': self.threshold
        }

class PerformanceMonitor:
    """
    Real-time performance monitoring system for Kenya Health AI
    Tracks metrics, generates alerts, and provides dashboard data
    """
    
    def __init__(self, max_history_size: int = 1000):
        self.max_history_size = max_history_size
        self.metrics_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history_size))
        self.alerts: deque = deque(maxlen=100)  # Keep last 100 alerts
        self.thresholds: Dict[str, Dict[str, float]] = {}
        self.lock = threading.Lock()
        
        # Performance targets for Kenya Health AI system
        self.setup_default_thresholds()
        
        # Current session metrics
        self.session_start = datetime.now()
        self.session_metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'avg_response_time': 0.0,
            'total_response_time': 0.0
        }
    
    def setup_default_thresholds(self):
        """Setup default performance thresholds for Kenya Health AI"""
        self.thresholds = {
            'workflow_execution_time': {
                'warning': 8.0,    # seconds
                'critical': 15.0   # seconds
            },
            'sql_generation_time': {
                'warning': 3.0,    # seconds
                'critical': 5.0    # seconds
            },
            'analysis_time': {
                'warning': 5.0,    # seconds
                'critical': 10.0   # seconds
            },
            'api_response_time': {
                'warning': 5.0,    # seconds
                'critical': 10.0   # seconds
            },
            'database_query_time': {
                'warning': 2.0,    # seconds
                'critical': 5.0    # seconds
            },
            'success_rate': {
                'warning': 85.0,   # percentage
                'critical': 70.0   # percentage
            },
            'memory_usage': {
                'warning': 80.0,   # percentage
                'critical': 90.0   # percentage
            }
        }
    
    def record_metric(self, metric_name: str, value: float, unit: str = 'seconds', metadata: Dict[str, Any] = None):
        """Record a performance metric"""
        with self.lock:
            metric = PerformanceMetric(
                timestamp=datetime.now(),
                metric_name=metric_name,
                value=value,
                unit=unit,
                metadata=metadata
            )
            
            self.metrics_history[metric_name].append(metric)
            
            # Update session metrics
            if metric_name == 'workflow_execution_time':
                self.session_metrics['total_requests'] += 1
                self.session_metrics['total_response_time'] += value
                self.session_metrics['avg_response_time'] = (
                    self.session_metrics['total_response_time'] / 
                    self.session_metrics['total_requests']
                )
                
                # Check if request was successful (assuming < 30s is successful)
                if value < 30.0:
                    self.session_metrics['successful_requests'] += 1
                else:
                    self.session_metrics['failed_requests'] += 1
            
            # Check thresholds and generate alerts
            self._check_thresholds(metric_name, value)
            
            logger.debug(f"Recorded metric: {metric_name} = {value} {unit}")
    
    def _check_thresholds(self, metric_name: str, value: float):
        """Check if metric value exceeds thresholds and generate alerts"""
        if metric_name not in self.thresholds:
            return
        
        thresholds = self.thresholds[metric_name]
        
        # Check critical threshold
        if 'critical' in thresholds:
            if (metric_name == 'success_rate' and value < thresholds['critical']) or \
               (metric_name != 'success_rate' and value > thresholds['critical']):
                self._generate_alert(
                    alert_type='threshold_exceeded',
                    severity='critical',
                    message=f"{metric_name} exceeded critical threshold: {value} vs {thresholds['critical']}",
                    metric_name=metric_name,
                    current_value=value,
                    threshold=thresholds['critical']
                )
        
        # Check warning threshold
        elif 'warning' in thresholds:
            if (metric_name == 'success_rate' and value < thresholds['warning']) or \
               (metric_name != 'success_rate' and value > thresholds['warning']):
                self._generate_alert(
                    alert_type='threshold_exceeded',
                    severity='warning',
                    message=f"{metric_name} exceeded warning threshold: {value} vs {thresholds['warning']}",
                    metric_name=metric_name,
                    current_value=value,
                    threshold=thresholds['warning']
                )
    
    def _generate_alert(self, alert_type: str, severity: str, message: str, 
                       metric_name: str, current_value: float, threshold: float):
        """Generate a system alert"""
        alert = SystemAlert(
            timestamp=datetime.now(),
            alert_type=alert_type,
            severity=severity,
            message=message,
            metric_name=metric_name,
            current_value=current_value,
            threshold=threshold
        )
        
        self.alerts.append(alert)
        
        # Log alert based on severity
        if severity == 'critical':
            logger.error(f"CRITICAL ALERT: {message}")
        elif severity == 'warning':
            logger.warning(f"WARNING: {message}")
        else:
            logger.info(f"ALERT: {message}")
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics summary"""
        with self.lock:
            current_metrics = {}
            
            for metric_name, history in self.metrics_history.items():
                if history:
                    recent_values = [m.value for m in list(history)[-10:]]  # Last 10 values
                    current_metrics[metric_name] = {
                        'current': recent_values[-1] if recent_values else 0,
                        'average_10': sum(recent_values) / len(recent_values) if recent_values else 0,
                        'min_10': min(recent_values) if recent_values else 0,
                        'max_10': max(recent_values) if recent_values else 0,
                        'count': len(history)
                    }
            
            # Add session metrics
            current_metrics['session'] = self.session_metrics.copy()
            current_metrics['session']['uptime_minutes'] = (
                datetime.now() - self.session_start
            ).total_seconds() / 60
            
            # Calculate success rate
            total_requests = self.session_metrics['total_requests']
            if total_requests > 0:
                success_rate = (self.session_metrics['successful_requests'] / total_requests) * 100
                current_metrics['session']['success_rate'] = success_rate
            else:
                current_metrics['session']['success_rate'] = 100.0
            
            return current_metrics
    
    def get_recent_alerts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent alerts"""
        with self.lock:
            recent_alerts = list(self.alerts)[-limit:]
            return [alert.to_dict() for alert in recent_alerts]
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary"""
        current_metrics = self.get_current_metrics()
        recent_alerts = self.get_recent_alerts()
        
        # Calculate overall system health score
        health_score = self._calculate_health_score(current_metrics)
        
        return {
            'timestamp': datetime.now().isoformat(),
            'health_score': health_score,
            'metrics': current_metrics,
            'recent_alerts': recent_alerts,
            'thresholds': self.thresholds,
            'system_status': self._get_system_status(health_score)
        }
    
    def _calculate_health_score(self, metrics: Dict[str, Any]) -> float:
        """Calculate overall system health score (0-100)"""
        score = 100.0
        
        # Check workflow performance (40% weight)
        if 'workflow_execution_time' in metrics:
            avg_time = metrics['workflow_execution_time'].get('average_10', 0)
            if avg_time > 15:  # Critical threshold
                score -= 40
            elif avg_time > 10:  # Target threshold
                score -= 20
            elif avg_time > 8:   # Warning threshold
                score -= 10
        
        # Check success rate (30% weight)
        session_success_rate = metrics.get('session', {}).get('success_rate', 100)
        if session_success_rate < 70:  # Critical
            score -= 30
        elif session_success_rate < 85:  # Warning
            score -= 15
        elif session_success_rate < 95:  # Good
            score -= 5
        
        # Check recent alerts (20% weight)
        recent_alerts = list(self.alerts)[-5:]  # Last 5 alerts
        critical_alerts = sum(1 for alert in recent_alerts if alert.severity == 'critical')
        warning_alerts = sum(1 for alert in recent_alerts if alert.severity == 'warning')
        
        score -= critical_alerts * 10
        score -= warning_alerts * 5
        
        # Check API response times (10% weight)
        if 'api_response_time' in metrics:
            avg_api_time = metrics['api_response_time'].get('average_10', 0)
            if avg_api_time > 10:  # Critical
                score -= 10
            elif avg_api_time > 5:  # Warning
                score -= 5
        
        return max(0, min(100, score))
    
    def _get_system_status(self, health_score: float) -> str:
        """Get system status based on health score"""
        if health_score >= 90:
            return 'excellent'
        elif health_score >= 75:
            return 'good'
        elif health_score >= 60:
            return 'fair'
        elif health_score >= 40:
            return 'poor'
        else:
            return 'critical'
    
    def save_metrics_to_file(self, filepath: str):
        """Save current metrics to JSON file"""
        summary = self.get_performance_summary()
        
        # Ensure directory exists
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        
        logger.info(f"Performance metrics saved to {filepath}")
    
    def reset_session_metrics(self):
        """Reset session metrics (useful for testing)"""
        with self.lock:
            self.session_start = datetime.now()
            self.session_metrics = {
                'total_requests': 0,
                'successful_requests': 0,
                'failed_requests': 0,
                'avg_response_time': 0.0,
                'total_response_time': 0.0
            }
            logger.info("Session metrics reset")

# Global performance monitor instance
performance_monitor = PerformanceMonitor()

def record_performance_metric(metric_name: str, value: float, unit: str = 'seconds', metadata: Dict[str, Any] = None):
    """Convenience function to record a performance metric"""
    performance_monitor.record_metric(metric_name, value, unit, metadata)

def get_performance_summary():
    """Convenience function to get performance summary"""
    return performance_monitor.get_performance_summary()
