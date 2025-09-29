"""Trained ML pricing model using Hong Kong data"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import TOLL_CONFIG, REVENUE_TARGET_HOURLY

class TrainedPricingModel:
    """ML-trained pricing model using Hong Kong historical data"""
    
    def __init__(self):
        self.ml_model = None
        self.load_trained_model()
        
    def load_trained_model(self):
        """Load the trained ML model with S3 support"""
        try:
            # Try to download latest model from S3
            from model_manager import model_manager
            model_manager.download_latest_model()
            
            # Check if model file exists
            import os
            if not os.path.exists('models/toll_pricing_model.pkl'):
                print("⚠️ No model available, using rule-based pricing")
                self.ml_model = None
                return
            
            # Suppress warnings for production
            import warnings
            warnings.filterwarnings('ignore')
            
            # Try importing ML components
            import numpy
            import sklearn
            from ml_trainer import TollPricingMLModel
            
            self.ml_model = TollPricingMLModel()
            
            # Try to load existing model
            if self.ml_model.load_model('models/toll_pricing_model.pkl'):
                model_info = model_manager.get_model_info()
                print(f"✅ Loaded ML model from {model_info['source']}")
            else:
                print("⚠️ Model loading failed, using rule-based pricing")
                self.ml_model = None
                
        except ImportError as e:
            print(f"⚠️ ML dependencies unavailable, using rule-based pricing")
            self.ml_model = None
        except Exception as e:
            print(f"⚠️ Model error, using rule-based pricing")
            self.ml_model = None
    
    def get_price_recommendation(self, state):
        """Get toll price recommendation"""
        
        if self.ml_model and self.ml_model.is_trained:
            # Use trained ML model
            try:
                # Convert simulation state to ML model format
                ml_state = {
                    'tunnel_congestion': state["tunnel_congestion"],
                    'nt_congestion': state.get("nt_congestion", state.get("tmr_congestion", 0.5)),
                    'time_of_day': state["time_of_day"],
                    'day_of_week': state["day_of_week"],
                    'is_peak': self._is_peak_hour(state["time_of_day"])
                }
                
                predicted_toll = self.ml_model.predict_toll(ml_state)
                
                # Apply constraints
                return max(TOLL_CONFIG.min_price, 
                          min(TOLL_CONFIG.max_price, predicted_toll))
                          
            except Exception as e:
                print(f"ML prediction error: {e}")
                return self._fallback_pricing(state)
        else:
            # Fallback to rule-based pricing
            return self._fallback_pricing(state)
    
    def _is_peak_hour(self, hour):
        """Check if current hour is peak time"""
        return (7 <= hour <= 9) or (17 <= hour <= 19)
    
    def _fallback_pricing(self, state):
        """Simple rule-based pricing as fallback"""
        
        tunnel_congestion = state["tunnel_congestion"]
        revenue_ratio = state["hourly_revenue"] / REVENUE_TARGET_HOURLY
        hour = state["time_of_day"]
        
        # Base price adjustment
        if tunnel_congestion > 0.8:
            price_multiplier = 1.6  # High congestion
        elif tunnel_congestion > 0.6:
            price_multiplier = 1.3  # Medium congestion
        elif tunnel_congestion < 0.3:
            price_multiplier = 0.8  # Low congestion
        else:
            price_multiplier = 1.0  # Normal
        
        # Peak hour adjustment
        if self._is_peak_hour(hour):
            price_multiplier *= 1.4
        elif 22 <= hour <= 6:  # Night hours
            price_multiplier *= 0.7
        
        # Revenue adjustment
        if revenue_ratio < 0.7:
            price_multiplier *= 1.2
        elif revenue_ratio > 1.3:
            price_multiplier *= 0.9
        
        new_price = TOLL_CONFIG.base_price * price_multiplier
        
        return max(TOLL_CONFIG.min_price, 
                  min(TOLL_CONFIG.max_price, new_price))
    
    def train_step(self, prev_state, action_price, new_state):
        """Training step (for compatibility)"""
        # In production, this would update the model
        pass