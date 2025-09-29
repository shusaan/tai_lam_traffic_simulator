"""Simple data processor without AWS dependencies"""

import json
import logging
from datetime import datetime
from typing import Dict, List

class TrafficDataProcessor:
    """Simple data processor for local simulation"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def simulate_traffic_stream(self, simulation_data: Dict):
        """Log simulation data locally"""
        self.logger.info(f"Traffic data: {simulation_data['timestamp']}")
    
    def store_traffic_data_batch(self, traffic_data_list: List[Dict]):
        """Store data locally"""
        self.logger.info(f"Stored {len(traffic_data_list)} records")
    
    def get_historical_traffic_data(self, hours: int = 24) -> List[Dict]:
        """Return empty list for local mode"""
        return []

class RealTimeDataStreamer:
    """Simple streamer for local simulation"""
    
    def __init__(self, data_processor):
        self.data_processor = data_processor
        self.is_streaming = False
        
    def start_streaming(self, simulator, scenario: str = "normal", duration_minutes: int = 60):
        """Start local streaming"""
        self.is_streaming = True
        
    def stop_streaming(self):
        """Stop streaming"""
        self.is_streaming = False