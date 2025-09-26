"""ML-based dynamic toll pricing model using reinforcement learning"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
import pickle
import os
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import TOLL_CONFIG, REVENUE_TARGET_HOURLY

class TollPricingAgent:
    """Reinforcement Learning agent for dynamic toll pricing"""
    
    def __init__(self, state_size: int = 7, action_size: int = 21):
        self.state_size = state_size
        self.action_size = action_size  # 21 discrete toll levels from 5-25 HKD
        self.memory = []
        self.epsilon = 1.0  # exploration rate
        self.epsilon_min = 0.01
        self.epsilon_decay = 0.995
        self.learning_rate = 0.001
        self.model = self._build_model()
        self.target_model = self._build_model()
        self.scaler = StandardScaler()
        
    def _build_model(self):
        """Build neural network for Q-learning"""
        model = keras.Sequential([
            layers.Dense(64, input_dim=self.state_size, activation='relu'),
            layers.Dense(64, activation='relu'),
            layers.Dense(32, activation='relu'),
            layers.Dense(self.action_size, activation='linear')
        ])
        model.compile(loss='mse', optimizer=keras.optimizers.Adam(lr=self.learning_rate))
        return model
    
    def _price_to_action(self, price: float) -> int:
        """Convert price to discrete action index"""
        return int((price - TOLL_CONFIG.min_price) / 
                  (TOLL_CONFIG.max_price - TOLL_CONFIG.min_price) * (self.action_size - 1))
    
    def _action_to_price(self, action: int) -> float:
        """Convert action index to price"""
        return TOLL_CONFIG.min_price + (action / (self.action_size - 1)) * \
               (TOLL_CONFIG.max_price - TOLL_CONFIG.min_price)
    
    def get_state_vector(self, state: Dict) -> np.array:
        """Convert simulation state to feature vector"""
        features = [
            state["tunnel_congestion"],
            state["tmr_congestion"], 
            state["nt_congestion"],
            state["current_toll"] / TOLL_CONFIG.max_price,  # normalized
            state["hourly_revenue"] / REVENUE_TARGET_HOURLY,  # normalized
            np.sin(2 * np.pi * state["time_of_day"] / 24),  # time encoding
            state["day_of_week"] / 7  # normalized
        ]
        return np.array(features).reshape(1, -1)
    
    def calculate_reward(self, prev_state: Dict, action: int, new_state: Dict) -> float:
        """Calculate reward for the pricing action"""
        new_price = self._action_to_price(action)
        
        # Revenue component (30% weight)
        revenue_ratio = new_state["hourly_revenue"] / REVENUE_TARGET_HOURLY
        revenue_reward = min(1.0, revenue_ratio) * 0.3
        
        # Traffic balance component (40% weight)
        tunnel_congestion = new_state["tunnel_congestion"]
        other_congestion = (new_state["tmr_congestion"] + new_state["nt_congestion"]) / 2
        
        # Reward balanced traffic distribution
        balance_score = 1.0 - abs(tunnel_congestion - other_congestion)
        balance_reward = balance_score * 0.4
        
        # Congestion penalty (20% weight)
        avg_congestion = (tunnel_congestion + other_congestion) / 2
        congestion_penalty = -max(0, avg_congestion - 0.8) * 0.2
        
        # Price stability reward (10% weight)
        price_change = abs(new_price - prev_state["current_toll"]) / prev_state["current_toll"]
        stability_reward = max(0, 1.0 - price_change * 5) * 0.1
        
        total_reward = revenue_reward + balance_reward + congestion_penalty + stability_reward
        return total_reward
    
    def act(self, state: Dict) -> float:
        """Choose toll price based on current state"""
        state_vector = self.get_state_vector(state)
        
        if np.random.random() <= self.epsilon:
            # Random exploration
            action = np.random.randint(0, self.action_size)
        else:
            # Exploit learned policy
            q_values = self.model.predict(state_vector, verbose=0)
            action = np.argmax(q_values[0])
        
        return self._action_to_price(action)
    
    def remember(self, state: Dict, action: int, reward: float, next_state: Dict, done: bool):
        """Store experience in replay memory"""
        self.memory.append((state, action, reward, next_state, done))
        if len(self.memory) > 10000:  # Limit memory size
            self.memory.pop(0)
    
    def replay(self, batch_size: int = 32):
        """Train the model on a batch of experiences"""
        if len(self.memory) < batch_size:
            return
        
        batch = np.random.choice(len(self.memory), batch_size, replace=False)
        
        states = []
        targets = []
        
        for i in batch:
            state, action, reward, next_state, done = self.memory[i]
            
            state_vector = self.get_state_vector(state)
            next_state_vector = self.get_state_vector(next_state)
            
            target = reward
            if not done:
                target += 0.95 * np.amax(self.target_model.predict(next_state_vector, verbose=0)[0])
            
            target_f = self.model.predict(state_vector, verbose=0)
            target_f[0][action] = target
            
            states.append(state_vector[0])
            targets.append(target_f[0])
        
        states = np.array(states)
        targets = np.array(targets)
        
        self.model.fit(states, targets, epochs=1, verbose=0)
        
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay
    
    def update_target_model(self):
        """Update target network"""
        self.target_model.set_weights(self.model.get_weights())
    
    def save_model(self, filepath: str):
        """Save trained model"""
        self.model.save(f"{filepath}_main.h5")
        self.target_model.save(f"{filepath}_target.h5")
        
        # Save scaler and other parameters
        with open(f"{filepath}_params.pkl", 'wb') as f:
            pickle.dump({
                'epsilon': self.epsilon,
                'scaler': self.scaler
            }, f)
    
    def load_model(self, filepath: str):
        """Load trained model"""
        if os.path.exists(f"{filepath}_main.h5"):
            self.model = keras.models.load_model(f"{filepath}_main.h5")
            self.target_model = keras.models.load_model(f"{filepath}_target.h5")
            
            with open(f"{filepath}_params.pkl", 'rb') as f:
                params = pickle.load(f)
                self.epsilon = params['epsilon']
                self.scaler = params['scaler']

class SimplePricingModel:
    """Simple rule-based pricing model as fallback"""
    
    def __init__(self):
        self.base_price = TOLL_CONFIG.base_price
        
    def calculate_price(self, state: Dict) -> float:
        """Calculate toll price using simple rules"""
        tunnel_congestion = state["tunnel_congestion"]
        revenue_ratio = state["hourly_revenue"] / REVENUE_TARGET_HOURLY
        
        # Base adjustment based on congestion
        if tunnel_congestion > 0.8:
            price_multiplier = 1.5  # Increase price to reduce demand
        elif tunnel_congestion < 0.3:
            price_multiplier = 0.8  # Decrease price to increase demand
        else:
            price_multiplier = 1.0
        
        # Revenue adjustment
        if revenue_ratio < 0.7:
            price_multiplier *= 1.2
        elif revenue_ratio > 1.3:
            price_multiplier *= 0.9
        
        # Time-of-day adjustment
        hour = state["time_of_day"]
        if 7 <= hour <= 9 or 17 <= hour <= 19:  # Rush hours
            price_multiplier *= 1.3
        elif 22 <= hour <= 6:  # Night hours
            price_multiplier *= 0.7
        
        new_price = self.base_price * price_multiplier
        
        # Apply constraints
        return max(TOLL_CONFIG.min_price, 
                  min(TOLL_CONFIG.max_price, new_price))

class HybridPricingModel:
    """Hybrid model combining ML and rule-based approaches"""
    
    def __init__(self):
        self.ml_agent = TollPricingAgent()
        self.simple_model = SimplePricingModel()
        self.use_ml = False
        self.training_data = []
        
    def get_price_recommendation(self, state: Dict) -> float:
        """Get price recommendation from hybrid model"""
        if self.use_ml and len(self.training_data) > 100:
            return self.ml_agent.act(state)
        else:
            return self.simple_model.calculate_price(state)
    
    def train_step(self, prev_state: Dict, action_price: float, new_state: Dict):
        """Training step for ML model"""
        if prev_state is not None:
            action = self.ml_agent._price_to_action(action_price)
            reward = self.ml_agent.calculate_reward(prev_state, action, new_state)
            
            self.ml_agent.remember(prev_state, action, reward, new_state, False)
            self.training_data.append((prev_state, action, reward, new_state))
            
            # Train periodically
            if len(self.training_data) % 50 == 0:
                self.ml_agent.replay()
                
            # Update target network periodically
            if len(self.training_data) % 200 == 0:
                self.ml_agent.update_target_model()
                
            # Switch to ML after sufficient training
            if len(self.training_data) > 100:
                self.use_ml = True