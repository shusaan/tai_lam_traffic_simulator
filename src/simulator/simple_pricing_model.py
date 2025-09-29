"""Simple pricing model without ML dependencies"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import TOLL_CONFIG, REVENUE_TARGET_HOURLY

class SimplePricingModel:
    """Simple rule-based pricing model"""
    
    def __init__(self):
        self.base_price = TOLL_CONFIG.base_price
        
    def get_price_recommendation(self, state):
        """Calculate toll price using simple rules"""
        tunnel_congestion = state["tunnel_congestion"]
        revenue_ratio = state["hourly_revenue"] / REVENUE_TARGET_HOURLY
        
        # Base adjustment based on congestion
        if tunnel_congestion > 0.8:
            price_multiplier = 1.5
        elif tunnel_congestion < 0.3:
            price_multiplier = 0.8
        else:
            price_multiplier = 1.0
        
        # Revenue adjustment
        if revenue_ratio < 0.7:
            price_multiplier *= 1.2
        elif revenue_ratio > 1.3:
            price_multiplier *= 0.9
        
        # Time-of-day adjustment
        hour = state["time_of_day"]
        if 7 <= hour <= 9 or 17 <= hour <= 19:
            price_multiplier *= 1.3
        elif 22 <= hour <= 6:
            price_multiplier *= 0.7
        
        new_price = self.base_price * price_multiplier
        return max(TOLL_CONFIG.min_price, min(TOLL_CONFIG.max_price, new_price))
    
    def train_step(self, prev_state, action_price, new_state):
        """No-op for compatibility"""
        pass