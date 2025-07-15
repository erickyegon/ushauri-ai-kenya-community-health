"""
County-specific configuration for Kenya Health AI System
Focused on Kisumu, Busia, and Vihiga counties
"""

from typing import Dict, List, Any

# Primary focus counties for the analysis period (Dec 2024 - Jun 2025)
FOCUS_COUNTIES = ['Kisumu', 'Busia', 'Vihiga']

# County-specific information
COUNTY_INFO = {
    'Kisumu': {
        'code': 'KIS',
        'region': 'Nyanza',
        'population_estimate': 1155574,
        'area_km2': 2085.9,
        'capital': 'Kisumu City',
        'characteristics': ['Urban-rural mix', 'High population density', 'Lake Victoria access'],
        'health_facilities': 156,
        'chw_target': 60,
        'color_code': '#1f77b4'  # Blue
    },
    'Busia': {
        'code': 'BUS', 
        'region': 'Western',
        'population_estimate': 893681,
        'area_km2': 1628.4,
        'capital': 'Busia Town',
        'characteristics': ['Border county', 'Cross-border health seeking', 'Agricultural economy'],
        'health_facilities': 89,
        'chw_target': 45,
        'color_code': '#ff7f0e'  # Orange
    },
    'Vihiga': {
        'code': 'VIH',
        'region': 'Western', 
        'population_estimate': 590013,
        'area_km2': 563.0,
        'capital': 'Vihiga Town',
        'characteristics': ['High population density', 'Limited facilities', 'Strong community engagement'],
        'health_facilities': 67,
        'chw_target': 35,
        'color_code': '#2ca02c'  # Green
    }
}

# Performance benchmarks by county (based on historical data)
COUNTY_BENCHMARKS = {
    'Kisumu': {
        'target_supervision_score': 78.0,
        'target_fp_score': 72.0,
        'target_immunization_score': 80.0,
        'target_tool_availability': 85.0
    },
    'Busia': {
        'target_supervision_score': 75.0,
        'target_fp_score': 68.0,
        'target_immunization_score': 75.0,
        'target_tool_availability': 80.0
    },
    'Vihiga': {
        'target_supervision_score': 76.0,
        'target_fp_score': 70.0,
        'target_immunization_score': 78.0,
        'target_tool_availability': 82.0
    }
}

# Service area priorities by county
COUNTY_PRIORITIES = {
    'Kisumu': ['Family Planning', 'Pneumonia Management', 'Nutrition'],
    'Busia': ['Malaria Treatment', 'Tool Availability', 'Family Planning'],
    'Vihiga': ['Immunization', 'Newborn Care', 'Community Engagement']
}

# Resource allocation targets
RESOURCE_TARGETS = {
    'tools_availability_target': 90.0,
    'ppe_availability_target': 95.0,
    'medicines_availability_target': 85.0,
    'supervision_frequency_target': 'monthly'
}

def get_county_info(county: str) -> Dict[str, Any]:
    """Get comprehensive information for a specific county"""
    return COUNTY_INFO.get(county, {})

def get_county_color(county: str) -> str:
    """Get the standard color code for a county"""
    return COUNTY_INFO.get(county, {}).get('color_code', '#666666')

def get_county_benchmark(county: str, metric: str) -> float:
    """Get performance benchmark for a county and metric"""
    return COUNTY_BENCHMARKS.get(county, {}).get(metric, 70.0)

def get_county_priorities(county: str) -> List[str]:
    """Get priority service areas for a county"""
    return COUNTY_PRIORITIES.get(county, [])

def validate_county(county: str) -> bool:
    """Validate if county is in focus list"""
    return county in FOCUS_COUNTIES

def get_all_counties() -> List[str]:
    """Get list of all focus counties"""
    return FOCUS_COUNTIES.copy()

# County comparison helpers
def get_county_comparison_data() -> Dict[str, Dict[str, Any]]:
    """Get data structure for county comparisons"""
    return {
        county: {
            'info': get_county_info(county),
            'benchmarks': COUNTY_BENCHMARKS.get(county, {}),
            'priorities': get_county_priorities(county)
        }
        for county in FOCUS_COUNTIES
    }

# Geographic groupings
REGIONAL_GROUPINGS = {
    'Western': ['Busia', 'Vihiga'],
    'Nyanza': ['Kisumu']
}

def get_counties_by_region(region: str) -> List[str]:
    """Get counties in a specific region"""
    return REGIONAL_GROUPINGS.get(region, [])

# Analysis period configuration
ANALYSIS_PERIOD = {
    'start_date': '2024-12-01',
    'end_date': '2025-06-30',
    'total_months': 7,
    'description': 'December 2024 to June 2025 analysis period'
}
