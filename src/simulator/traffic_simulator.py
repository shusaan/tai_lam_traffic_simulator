"""Core traffic simulation engine for Tai Lam Tunnel system"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import random
import math

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import ROADS, SCENARIOS, TOLL_CONFIG

@dataclass
class Vehicle:
    """Individual vehicle in the simulation"""
    id: str
    origin: str
    destination: str
    departure_time: datetime
    route_preference: float  # 0-1, higher = more price sensitive
    value_of_time: float  # HKD per minute

class Road:
    """Road segment with traffic flow dynamics"""
    
    def __init__(self, config):
        self.config = config
        self.current_vehicles = 0
        self.queue_length = 0
        self.travel_time_history = []
        self.flow_rate = 0  # vehicles per minute
        
    def calculate_travel_time(self, weather_factor: float = 1.0) -> float:
        """Calculate current travel time based on congestion"""
        congestion_ratio = self.current_vehicles / self.config.capacity
        
        # BPR (Bureau of Public Roads) function for travel time
        congestion_factor = 1 + 0.15 * (congestion_ratio ** 4)
        travel_time = self.config.base_travel_time * congestion_factor * weather_factor
        
        return max(travel_time, self.config.base_travel_time)
    
    def add_vehicle(self):
        """Add vehicle to road"""
        self.current_vehicles += 1
        
    def remove_vehicle(self):
        """Remove vehicle from road"""
        self.current_vehicles = max(0, self.current_vehicles - 1)
    
    def get_congestion_level(self) -> float:
        """Return congestion level (0-1)"""
        return min(1.0, self.current_vehicles / self.config.capacity)

class TrafficSimulator:
    """Main traffic simulation engine"""
    
    def __init__(self):
        self.roads = {name: Road(config) for name, config in ROADS.items()}
        self.vehicles = []
        self.current_time = datetime.now()
        self.toll_price = TOLL_CONFIG.base_price
        self.revenue = 0.0
        self.traffic_data = []
        
    def generate_demand(self, scenario: str, time_of_day: int) -> int:
        """Generate vehicle demand based on scenario and time"""
        base_demand = self._get_base_demand(time_of_day)
        scenario_config = SCENARIOS.get(scenario, SCENARIOS["normal"])
        
        demand = int(base_demand * scenario_config["demand_multiplier"])
        return max(0, demand + np.random.poisson(demand * 0.1))
    
    def _get_base_demand(self, hour: int) -> int:
        """Base hourly demand pattern"""
        # Typical Hong Kong traffic pattern
        demand_pattern = {
            0: 50, 1: 30, 2: 20, 3: 15, 4: 25, 5: 80,
            6: 200, 7: 350, 8: 400, 9: 250, 10: 180, 11: 200,
            12: 220, 13: 200, 14: 180, 15: 200, 16: 280, 17: 380,
            18: 420, 19: 300, 20: 200, 21: 150, 22: 120, 23: 80
        }
        return demand_pattern.get(hour, 100)
    
    def route_choice_model(self, vehicle: Vehicle, scenario: str) -> str:
        """Determine vehicle route based on toll, congestion, and preferences"""
        weather_factor = SCENARIOS[scenario]["weather_factor"]
        
        # Calculate generalized cost for each route
        routes = {}
        
        # Tai Lam Tunnel (toll road)
        tunnel_time = self.roads["tai_lam_tunnel"].calculate_travel_time(weather_factor)
        tunnel_cost = self.toll_price + (tunnel_time * vehicle.value_of_time)
        routes["tai_lam_tunnel"] = tunnel_cost
        
        # Tuen Mun Road (free)
        tmr_time = self.roads["tuen_mun_road"].calculate_travel_time(weather_factor)
        tmr_cost = tmr_time * vehicle.value_of_time
        routes["tuen_mun_road"] = tmr_cost
        
        # NT Circular Road (free)
        nt_time = self.roads["nt_circular_road"].calculate_travel_time(weather_factor)
        nt_cost = nt_time * vehicle.value_of_time
        routes["nt_circular_road"] = nt_cost
        
        # Logit choice model
        utilities = {route: -cost * vehicle.route_preference for route, cost in routes.items()}
        exp_utilities = {route: math.exp(utility) for route, utility in utilities.items()}
        total_exp = sum(exp_utilities.values())
        
        probabilities = {route: exp_u / total_exp for route, exp_u in exp_utilities.items()}
        
        # Random choice based on probabilities
        rand = random.random()
        cumulative = 0
        for route, prob in probabilities.items():
            cumulative += prob
            if rand <= cumulative:
                return route
        
        return "tuen_mun_road"  # fallback
    
    def create_vehicle(self, vehicle_id: str) -> Vehicle:
        """Create a new vehicle with random characteristics"""
        return Vehicle(
            id=vehicle_id,
            origin="tuen_mun",
            destination="tsuen_wan",
            departure_time=self.current_time,
            route_preference=np.random.beta(2, 5),  # Most people somewhat price sensitive
            value_of_time=np.random.normal(2.5, 0.8)  # HKD per minute
        )
    
    def simulate_step(self, scenario: str = "normal") -> Dict:
        """Simulate one time step (1 minute)"""
        hour = self.current_time.hour
        minute_demand = self.generate_demand(scenario, hour) / 60  # per minute
        
        # Generate new vehicles
        new_vehicles = np.random.poisson(minute_demand)
        for i in range(new_vehicles):
            vehicle = self.create_vehicle(f"{self.current_time.timestamp()}_{i}")
            chosen_route = self.route_choice_model(vehicle, scenario)
            
            # Add to chosen road
            self.roads[chosen_route].add_vehicle()
            
            # Track revenue for tunnel
            if chosen_route == "tai_lam_tunnel":
                self.revenue += self.toll_price
            
            self.vehicles.append((vehicle, chosen_route))
        
        # Remove vehicles that completed their journey
        completed_vehicles = []
        for i, (vehicle, route) in enumerate(self.vehicles):
            travel_time = self.roads[route].calculate_travel_time(
                SCENARIOS[scenario]["weather_factor"]
            )
            
            if (self.current_time - vehicle.departure_time).total_seconds() >= travel_time * 60:
                self.roads[route].remove_vehicle()
                completed_vehicles.append(i)
        
        # Remove completed vehicles
        for i in reversed(completed_vehicles):
            self.vehicles.pop(i)
        
        # Collect traffic data
        traffic_snapshot = {
            "timestamp": self.current_time,
            "scenario": scenario,
            "toll_price": self.toll_price,
            "revenue": self.revenue,
            "roads": {
                name: {
                    "vehicles": road.current_vehicles,
                    "congestion": road.get_congestion_level(),
                    "travel_time": road.calculate_travel_time(SCENARIOS[scenario]["weather_factor"])
                }
                for name, road in self.roads.items()
            }
        }
        
        self.traffic_data.append(traffic_snapshot)
        self.current_time += timedelta(minutes=1)
        
        return traffic_snapshot
    
    def get_current_state(self) -> Dict:
        """Get current simulation state for ML model"""
        return {
            "tunnel_congestion": self.roads["tai_lam_tunnel"].get_congestion_level(),
            "tmr_congestion": self.roads["tuen_mun_road"].get_congestion_level(),
            "nt_congestion": self.roads["nt_circular_road"].get_congestion_level(),
            "current_toll": self.toll_price,
            "hourly_revenue": self.revenue,
            "time_of_day": self.current_time.hour,
            "day_of_week": self.current_time.weekday()
        }
    
    def update_toll_price(self, new_price: float):
        """Update toll price with constraints"""
        # Apply maximum change constraint
        max_change = self.toll_price * TOLL_CONFIG.max_change_percent
        new_price = max(
            self.toll_price - max_change,
            min(self.toll_price + max_change, new_price)
        )
        
        # Apply min/max constraints
        self.toll_price = max(
            TOLL_CONFIG.min_price,
            min(TOLL_CONFIG.max_price, new_price)
        )
    
    def reset_simulation(self):
        """Reset simulation to initial state"""
        self.roads = {name: Road(config) for name, config in ROADS.items()}
        self.vehicles = []
        self.current_time = datetime.now()
        self.toll_price = TOLL_CONFIG.base_price
        self.revenue = 0.0
        self.traffic_data = []