"""
Demo database module for Hugging Face Spaces deployment
Uses sample data instead of live PostgreSQL connection
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import random

logger = logging.getLogger(__name__)

# Sample data for demo
SAMPLE_CHW_DATA = [
    {"chv_name": "Mary Achieng", "county": "Kisumu", "calc_assessment_score": 85.2, "calc_family_planning_score": 88.0, "calc_immunization_score": 82.5},
    {"chv_name": "John Ochieng", "county": "Kisumu", "calc_assessment_score": 78.5, "calc_family_planning_score": 75.0, "calc_immunization_score": 80.0},
    {"chv_name": "Grace Wanjiku", "county": "Busia", "calc_assessment_score": 92.1, "calc_family_planning_score": 95.0, "calc_immunization_score": 89.0},
    {"chv_name": "Peter Mwangi", "county": "Busia", "calc_assessment_score": 67.8, "calc_family_planning_score": 70.0, "calc_immunization_score": 65.0},
    {"chv_name": "Sarah Njeri", "county": "Vihiga", "calc_assessment_score": 81.3, "calc_family_planning_score": 83.0, "calc_immunization_score": 79.0},
    {"chv_name": "David Kiprotich", "county": "Vihiga", "calc_assessment_score": 74.6, "calc_family_planning_score": 72.0, "calc_immunization_score": 77.0},
]

def connect_db():
    """Demo database connection - returns True for demo mode"""
    logger.info("Demo mode: Using sample data instead of live database")
    return True

def execute_sql_query(engine, query):
    """Execute demo SQL query using sample data"""
    try:
        logger.info(f"Demo mode: Simulating SQL query execution")
        
        # Generate sample data based on query patterns
        if "county" in query.lower() and "group by county" in query.lower():
            # County comparison query
            data = pd.DataFrame([
                {"county": "Kisumu", "total_chws": 45, "avg_performance": 81.8, "total_supervisions": 180},
                {"county": "Busia", "total_chws": 38, "avg_performance": 79.9, "total_supervisions": 152},
                {"county": "Vihiga", "total_chws": 42, "avg_performance": 77.9, "total_supervisions": 168}
            ])
        
        elif "chv_name" in query.lower():
            # Individual CHW query
            data = pd.DataFrame(SAMPLE_CHW_DATA)
            
            # Add some random variation
            for idx in range(len(data)):
                data.loc[idx, 'reported'] = datetime.now() - timedelta(days=random.randint(1, 30))
                data.loc[idx, 'chv_uuid'] = f"CHW-{idx+1:03d}"
        
        elif "monthly" in query.lower() or "trend" in query.lower():
            # Trend analysis query
            months = ['2024-12', '2025-01', '2025-02', '2025-03', '2025-04', '2025-05']
            data = pd.DataFrame([
                {"month": month, "avg_score": 75 + random.uniform(-5, 10), "total_supervisions": random.randint(80, 120)}
                for month in months
            ])
        
        else:
            # Default sample data
            data = pd.DataFrame(SAMPLE_CHW_DATA)
        
        logger.info(f"Demo mode: Returning {len(data)} sample records")
        return data
        
    except Exception as e:
        logger.error(f"Demo query simulation error: {e}")
        return pd.DataFrame()

def get_dashboard_metrics():
    """Get demo dashboard metrics"""
    return {
        "total_chws": 125,
        "total_supervisions": 500,
        "avg_score": 79.8,
        "counties": 3
    }

def check_database_health():
    """Demo database health check"""
    return {"status": "healthy", "message": "Demo mode: Sample data ready"}

def test_connection():
    """Demo connection test"""
    return True, "Demo mode: Connection successful"

# Additional demo functions for compatibility
def check_database_health_detailed(engine):
    """Detailed health check for demo mode"""
    return {
        "connection": True,
        "tables": ["supervision", "chw_profiles", "resources"],
        "total_records": 500,
        "last_update": datetime.now().isoformat()
    }

def get_county_performance():
    """Get demo county performance data"""
    return pd.DataFrame([
        {"county": "Kisumu", "performance": 81.8, "chws": 45, "status": "Good"},
        {"county": "Busia", "performance": 79.9, "chws": 38, "status": "Good"},
        {"county": "Vihiga", "performance": 77.9, "chws": 42, "status": "Needs Improvement"}
    ])

def get_recent_activities():
    """Get demo recent activities"""
    activities = [
        "CHW supervision completed in Kisumu",
        "Resource distribution in Busia county",
        "Training session conducted in Vihiga",
        "Performance review meeting held",
        "New CHW onboarded in Kisumu"
    ]
    
    return pd.DataFrame([
        {
            "activity": activity,
            "timestamp": datetime.now() - timedelta(hours=random.randint(1, 48)),
            "county": random.choice(["Kisumu", "Busia", "Vihiga"])
        }
        for activity in activities
    ])
