"""Configuration settings for Tai Lam Traffic Simulator"""

import os
from dataclasses import dataclass
from typing import Dict, List

@dataclass
class RoadConfig:
    """Configuration for road segments"""
    name: str
    capacity: int  # vehicles per hour
    length_km: float
    base_travel_time: float  # minutes
    coordinates: List[tuple]  # lat, lng points for visualization

@dataclass
class TollConfig:
    """Toll pricing configuration"""
    base_price: float
    min_price: float
    max_price: float
    max_change_percent: float = 0.20  # 20% max change per adjustment

# Hong Kong road network configuration
ROADS = {
    "tai_lam_tunnel": RoadConfig(
        name="Tai Lam Tunnel",
        capacity=3000,  # vehicles/hour
        length_km=3.8,
        base_travel_time=4.0,
        coordinates=[(22.3964, 114.0294), (22.4089, 114.0156)]
    ),
    "tuen_mun_road": RoadConfig(
        name="Tuen Mun Road",
        capacity=4500,
        length_km=15.2,
        base_travel_time=18.0,
        coordinates=[(22.3964, 114.0294), (22.4500, 114.0800), (22.4089, 114.0156)]
    ),
    "nt_circular_road": RoadConfig(
        name="NT Circular Road",
        capacity=3500,
        length_km=12.8,
        base_travel_time=16.0,
        coordinates=[(22.3964, 114.0294), (22.4200, 114.0600), (22.4089, 114.0156)]
    )
}

# Toll configuration
TOLL_CONFIG = TollConfig(
    base_price=30.0,  # HKD
    min_price=18.0,
    max_price=55.0,
    max_change_percent=0.20
)

# Traffic scenarios
SCENARIOS = {
    "normal": {"demand_multiplier": 1.0, "weather_factor": 1.0},
    "rush_hour": {"demand_multiplier": 2.5, "weather_factor": 1.0},
    "rainstorm": {"demand_multiplier": 1.2, "weather_factor": 1.8},
    "concert_night": {"demand_multiplier": 3.0, "weather_factor": 1.0}
}

# AWS Configuration
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "ap-east-1")
S3_MODEL_BUCKET = os.getenv("MODEL_S3_BUCKET", "tai-lam-poc-models")
DYNAMODB_TABLE_TRAFFIC = os.getenv("TRAFFIC_TABLE", "tai-lam-poc-traffic")
DYNAMODB_TABLE_TOLLS = os.getenv("TOLL_TABLE", "tai-lam-poc-tolls")
API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "https://api.example.com/dev/toll")

# Simulation parameters
SIMULATION_STEP_MINUTES = 1
TOLL_ADJUSTMENT_INTERVAL = 15  # minutes
REVENUE_TARGET_HOURLY = 50000  # HKD
