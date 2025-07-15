"""
Geographic Configuration for Kenya Health AI System
Contains coordinates, boundaries, and geographic data for Kisumu, Busia, and Vihiga counties
"""

from typing import Dict, List, Tuple, Any

# County center coordinates (longitude, latitude)
COUNTY_CENTERS = {
    'Kisumu': {
        'longitude': 34.7778573178751,
        'latitude': -0.197126,
        'center': [34.7778573178751, -0.197126]
    },
    'Busia': {
        'longitude': 34.26479520608315,
        'latitude': 0.3712048,
        'center': [34.26479520608315, 0.3712048]
    },
    'Vihiga': {
        'longitude': 34.708033906814826,
        'latitude': 0.0831199,
        'center': [34.708033906814826, 0.0831199]
    }
}

# County administrative information
COUNTY_ADMIN_DATA = {
    'Kisumu': {
        'name': 'Kisumu',
        'capital': 'Kisumu',
        'code': 42,
        'sub_counties': [
            'Kisumu central',
            'Kisumu east',
            'Kisumu west',
            'Mohoroni',
            'Nyakach',
            'Nyando',
            'Seme'
        ]
    },
    'Busia': {
        'name': 'Busia',
        'capital': 'Busia',
        'code': 40,
        'sub_counties': [
            'Budalangi',
            'Butula',
            'Funyula',
            'Nambele',
            'Teso North',
            'Teso South'
        ]
    },
    'Vihiga': {
        'name': 'Vihiga',
        'capital': 'Vihiga',
        'code': 38,
        'sub_counties': [
            'Emuhaya',
            'Hamisi',
            'Luanda',
            'Sabatia',
            'Vihiga'
        ]
    }
}

# Geographic boundaries (approximate bounding boxes)
COUNTY_BOUNDARIES = {
    'Kisumu': {
        'min_longitude': 34.4388,
        'max_longitude': 35.3433,
        'min_latitude': -0.4168,
        'max_latitude': 0.0226,
        'bbox': [34.4388, -0.4168, 35.3433, 0.0226]  # [min_lon, min_lat, max_lon, max_lat]
    },
    'Busia': {
        'min_longitude': 33.9519,
        'max_longitude': 34.7891,
        'min_latitude': -0.0328,
        'max_latitude': 0.8042,
        'bbox': [33.9519, -0.0328, 34.7891, 0.8042]
    },
    'Vihiga': {
        'min_longitude': 34.5341,
        'max_longitude': 35.0123,
        'min_latitude': -0.0166,
        'max_latitude': 0.2831,
        'bbox': [34.5341, -0.0166, 35.0123, 0.2831]
    }
}

# Regional groupings for analysis
REGIONAL_CLUSTERS = {
    'Lake_Victoria_Region': ['Kisumu', 'Busia'],
    'Western_Highlands': ['Vihiga'],
    'Border_Counties': ['Busia'],
    'Urban_Centers': ['Kisumu']
}

# Distance matrix between county centers (approximate km)
INTER_COUNTY_DISTANCES = {
    ('Kisumu', 'Busia'): 85,
    ('Kisumu', 'Vihiga'): 45,
    ('Busia', 'Vihiga'): 65,
    ('Busia', 'Kisumu'): 85,
    ('Vihiga', 'Kisumu'): 45,
    ('Vihiga', 'Busia'): 65
}

# Health facility distribution zones (based on geographic accessibility)
HEALTH_ZONES = {
    'Kisumu': {
        'urban_zone': {
            'description': 'Kisumu City and immediate surroundings',
            'accessibility': 'high',
            'population_density': 'high'
        },
        'peri_urban_zone': {
            'description': 'Areas around Kisumu City',
            'accessibility': 'medium',
            'population_density': 'medium'
        },
        'rural_zone': {
            'description': 'Rural areas and fishing communities',
            'accessibility': 'low',
            'population_density': 'low'
        }
    },
    'Busia': {
        'border_zone': {
            'description': 'Areas near Uganda border',
            'accessibility': 'medium',
            'population_density': 'medium',
            'special_considerations': ['cross_border_health_seeking']
        },
        'agricultural_zone': {
            'description': 'Rural agricultural areas',
            'accessibility': 'low',
            'population_density': 'low'
        }
    },
    'Vihiga': {
        'highland_zone': {
            'description': 'Highland areas with dense population',
            'accessibility': 'medium',
            'population_density': 'very_high'
        },
        'valley_zone': {
            'description': 'Valley areas with scattered settlements',
            'accessibility': 'low',
            'population_density': 'medium'
        }
    }
}

def get_county_center(county: str) -> Tuple[float, float]:
    """Get the center coordinates for a county"""
    if county in COUNTY_CENTERS:
        center = COUNTY_CENTERS[county]['center']
        return (center[0], center[1])  # (longitude, latitude)
    return (0.0, 0.0)

def get_county_bbox(county: str) -> List[float]:
    """Get bounding box for a county [min_lon, min_lat, max_lon, max_lat]"""
    return COUNTY_BOUNDARIES.get(county, {}).get('bbox', [0, 0, 0, 0])

def get_distance_between_counties(county1: str, county2: str) -> int:
    """Get approximate distance between two counties in kilometers"""
    key1 = (county1, county2)
    key2 = (county2, county1)
    return INTER_COUNTY_DISTANCES.get(key1, INTER_COUNTY_DISTANCES.get(key2, 0))

def get_sub_counties(county: str) -> List[str]:
    """Get list of sub-counties for a given county"""
    return COUNTY_ADMIN_DATA.get(county, {}).get('sub_counties', [])

def get_county_code(county: str) -> int:
    """Get official county code"""
    return COUNTY_ADMIN_DATA.get(county, {}).get('code', 0)

def is_border_county(county: str) -> bool:
    """Check if county is a border county"""
    return county in REGIONAL_CLUSTERS.get('Border_Counties', [])

def is_urban_county(county: str) -> bool:
    """Check if county has major urban centers"""
    return county in REGIONAL_CLUSTERS.get('Urban_Centers', [])

def get_health_zones(county: str) -> Dict[str, Any]:
    """Get health facility zones for a county"""
    return HEALTH_ZONES.get(county, {})

# Map visualization settings
MAP_SETTINGS = {
    'default_zoom': 9,
    'center_point': [34.5, 0.1],  # Approximate center of the three counties
    'tile_layer': 'OpenStreetMap',
    'county_colors': {
        'Kisumu': '#1f77b4',  # Blue
        'Busia': '#ff7f0e',   # Orange
        'Vihiga': '#2ca02c'   # Green
    }
}

# GeoJSON file paths (relative to project root)
GEOJSON_PATHS = {
    'Kisumu': 'data/geographic/kisumu.geojson',
    'Busia': 'data/geographic/busia.geojson',
    'Vihiga': 'data/geographic/vihiga.geojson'
}
