"""Q-Learning Reinforcement Learning Agent for Dynamic Toll Pricing"""

import numpy as np
import json
import pickle
from collections import defaultdict
from datetime import datetime
import boto3
import os

class QLearningTollAgent:
    def __init__(self, learning_rate=0.1, discount_factor=0.95, epsilon=0.1):
        """Initialize Q-Learning agent for toll pricing"""
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.epsilon = epsilon  # exploration rate
        
        # Q-table: state -> action -> Q-value
        self.q_table = defaultdict(lambda: defaultdict(float))
        
        # Action space: toll price adjustments
        self.actions = [-5, -2, -1, 0, 1, 2, 5]  # HKD adjustments
        
        # State discretization
        self.congestion_bins = [0.0, 0.3, 0.6, 0.8, 1.0]
        self.revenue_bins = [0, 25000, 50000, 75000, 100000]  # HKD per hour
        self.time_bins = [0, 6, 9, 17, 20, 24]  # Hour of day
        
        # AWS clients
        self.s3 = boto3.client('s3')
        self.dynamodb = boto3.resource('dynamodb')
        
    def discretize_state(self, traffic_state):
        """Convert continuous state to discrete state for Q-table"""
        congestion = traffic_state.get('avg_congestion', 0.5)
        revenue = traffic_state.get('revenue_per_hour', 30000)
        hour = datetime.now().hour
        vehicles = traffic_state.get('total_vehicles', 1000)
        
        # Discretize continuous values
        congestion_bin = np.digitize(congestion, self.congestion_bins) - 1
        revenue_bin = np.digitize(revenue, self.revenue_bins) - 1
        time_bin = np.digitize(hour, self.time_bins) - 1
        vehicle_bin = min(int(vehicles / 500), 4)  # 0-4 bins
        
        return (congestion_bin, revenue_bin, time_bin, vehicle_bin)
    
    def get_action(self, state, explore=True):
        """Select action using epsilon-greedy policy"""
        if explore and np.random.random() < self.epsilon:
            # Exploration: random action
            return np.random.choice(self.actions)
        else:
            # Exploitation: best known action
            state_key = str(state)
            if state_key not in self.q_table:
                return 0  # No adjustment if state unseen
            
            q_values = self.q_table[state_key]
            if not q_values:
                return 0
            
            best_action = max(q_values.keys(), key=lambda a: q_values[a])
            return best_action
    
    def calculate_reward(self, old_state, new_state, action, toll_price):
        """Calculate reward for the action taken"""
        # Multi-objective reward function
        
        # Revenue component (primary objective)
        old_revenue = old_state.get('revenue_per_hour', 30000)
        new_revenue = new_state.get('revenue_per_hour', 30000)
        revenue_improvement = (new_revenue - old_revenue) / 1000  # Scale down
        
        # Congestion reduction component
        old_congestion = old_state.get('avg_congestion', 0.5)
        new_congestion = new_state.get('avg_congestion', 0.5)
        congestion_improvement = (old_congestion - new_congestion) * 100
        
        # Traffic distribution balance
        traffic_balance = self.calculate_traffic_balance(new_state)
        
        # Penalty for extreme toll prices
        toll_penalty = 0
        if toll_price < 18 or toll_price > 55:
            toll_penalty = -10
        
        # Combined reward
        reward = (
            revenue_improvement * 0.5 +           # Revenue weight: 50%
            congestion_improvement * 0.3 +        # Congestion weight: 30%
            traffic_balance * 0.2 +               # Balance weight: 20%
            toll_penalty
        )
        
        return reward
    
    def calculate_traffic_balance(self, state):
        """Calculate traffic distribution balance score"""
        roads = state.get('roads', {})
        if len(roads) < 3:
            return 0
        
        # Get congestion levels for all roads
        congestions = [road.get('congestion', 0.5) for road in roads.values()]
        
        # Reward balanced congestion (lower variance is better)
        variance = np.var(congestions)
        balance_score = max(0, 10 - variance * 100)  # Higher score for lower variance
        
        return balance_score
    
    def update_q_value(self, state, action, reward, next_state):
        """Update Q-value using Q-learning formula"""
        state_key = str(state)
        next_state_key = str(next_state)
        
        # Current Q-value
        current_q = self.q_table[state_key][action]
        
        # Maximum Q-value for next state
        if next_state_key in self.q_table and self.q_table[next_state_key]:
            max_next_q = max(self.q_table[next_state_key].values())
        else:
            max_next_q = 0
        
        # Q-learning update
        new_q = current_q + self.learning_rate * (
            reward + self.discount_factor * max_next_q - current_q
        )
        
        self.q_table[state_key][action] = new_q
    
    def train_step(self, old_state, action, reward, new_state):
        """Single training step"""
        discrete_old_state = self.discretize_state(old_state)
        discrete_new_state = self.discretize_state(new_state)
        
        self.update_q_value(discrete_old_state, action, reward, discrete_new_state)
        
        # Decay exploration rate
        self.epsilon = max(0.01, self.epsilon * 0.995)
    
    def get_toll_recommendation(self, traffic_state, current_toll):
        """Get toll price recommendation using RL agent"""
        discrete_state = self.discretize_state(traffic_state)
        action = self.get_action(discrete_state, explore=True)
        
        # Apply action to current toll
        new_toll = current_toll + action
        
        # Ensure toll is within bounds
        new_toll = max(18.0, min(55.0, new_toll))
        
        return new_toll, action
    
    def save_model(self, bucket_name, key='rl_toll_agent.pkl'):
        """Save Q-table to S3"""
        try:
            # Convert defaultdict to regular dict for serialization
            q_table_dict = {
                state: dict(actions) for state, actions in self.q_table.items()
            }
            
            model_data = {
                'q_table': q_table_dict,
                'learning_rate': self.learning_rate,
                'discount_factor': self.discount_factor,
                'epsilon': self.epsilon,
                'actions': self.actions,
                'timestamp': datetime.now().isoformat()
            }
            
            # Serialize and upload
            model_bytes = pickle.dumps(model_data)
            self.s3.put_object(Bucket=bucket_name, Key=key, Body=model_bytes)
            
            print(f"RL model saved to s3://{bucket_name}/{key}")
            return True
            
        except Exception as e:
            print(f"Error saving RL model: {str(e)}")
            return False
    
    def load_model(self, bucket_name, key='rl_toll_agent.pkl'):
        """Load Q-table from S3"""
        try:
            response = self.s3.get_object(Bucket=bucket_name, Key=key)
            model_data = pickle.loads(response['Body'].read())
            
            # Restore Q-table
            self.q_table = defaultdict(lambda: defaultdict(float))
            for state, actions in model_data['q_table'].items():
                for action, q_value in actions.items():
                    self.q_table[state][action] = q_value
            
            # Restore parameters
            self.learning_rate = model_data.get('learning_rate', 0.1)
            self.discount_factor = model_data.get('discount_factor', 0.95)
            self.epsilon = model_data.get('epsilon', 0.1)
            
            print(f"RL model loaded from s3://{bucket_name}/{key}")
            return True
            
        except Exception as e:
            print(f"Error loading RL model: {str(e)}")
            return False
    
    def get_model_stats(self):
        """Get statistics about the learned model"""
        total_states = len(self.q_table)
        total_state_actions = sum(len(actions) for actions in self.q_table.values())
        
        return {
            'total_states': total_states,
            'total_state_actions': total_state_actions,
            'epsilon': self.epsilon,
            'learning_rate': self.learning_rate,
            'discount_factor': self.discount_factor
        }