"""Model Updater for Continuous Learning from Latest Data"""

import boto3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pickle
import json
from decimal import Decimal
from .q_learning_agent import QLearningTollAgent

class ModelUpdater:
    def __init__(self, region='ap-east-1'):
        """Initialize model updater with AWS clients"""
        self.s3 = boto3.client('s3', region_name=region)
        self.dynamodb = boto3.resource('dynamodb', region_name=region)
        
        # Table names
        self.traffic_table_name = 'tai-lam-poc-traffic'
        self.toll_table_name = 'tai-lam-poc-tolls'
        
        # RL Agent
        self.rl_agent = QLearningTollAgent()
        
    def get_latest_data(self, hours_back=24):
        """Get latest traffic and toll data from DynamoDB"""
        try:
            # Calculate time range
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours_back)
            
            # Get traffic data
            traffic_table = self.dynamodb.Table(self.traffic_table_name)
            traffic_response = traffic_table.scan(
                FilterExpression='#ts BETWEEN :start AND :end',
                ExpressionAttributeNames={'#ts': 'timestamp'},
                ExpressionAttributeValues={
                    ':start': start_time.isoformat(),
                    ':end': end_time.isoformat()
                }
            )
            
            # Get toll data
            toll_table = self.dynamodb.Table(self.toll_table_name)
            toll_response = toll_table.scan(
                FilterExpression='#ts BETWEEN :start AND :end',
                ExpressionAttributeNames={'#ts': 'timestamp'},
                ExpressionAttributeValues={
                    ':start': start_time.isoformat(),
                    ':end': end_time.isoformat()
                }
            )
            
            return traffic_response['Items'], toll_response['Items']
            
        except Exception as e:
            print(f"Error getting latest data: {str(e)}")
            return [], []
    
    def process_training_data(self, traffic_data, toll_data):
        """Process raw data into training episodes"""
        episodes = []
        
        # Sort data by timestamp
        traffic_data = sorted(traffic_data, key=lambda x: x['timestamp'])
        toll_data = sorted(toll_data, key=lambda x: x['timestamp'])
        
        # Create episodes from sequential data
        for i in range(len(traffic_data) - 1):
            current_traffic = traffic_data[i]
            next_traffic = traffic_data[i + 1]
            
            # Find corresponding toll data
            current_toll = self.find_nearest_toll(current_traffic['timestamp'], toll_data)
            next_toll = self.find_nearest_toll(next_traffic['timestamp'], toll_data)
            
            if current_toll and next_toll:
                # Create episode
                episode = {
                    'state': self.extract_state(current_traffic),
                    'action': float(next_toll['toll_price']) - float(current_toll['toll_price']),
                    'next_state': self.extract_state(next_traffic),
                    'toll_price': float(next_toll['toll_price'])
                }
                episodes.append(episode)
        
        return episodes
    
    def find_nearest_toll(self, timestamp, toll_data):
        """Find toll data nearest to given timestamp"""
        target_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        
        nearest_toll = None
        min_diff = float('inf')
        
        for toll in toll_data:
            toll_time = datetime.fromisoformat(toll['timestamp'].replace('Z', '+00:00'))
            diff = abs((target_time - toll_time).total_seconds())
            
            if diff < min_diff:
                min_diff = diff
                nearest_toll = toll
        
        return nearest_toll
    
    def extract_state(self, traffic_data):
        """Extract state features from traffic data"""
        try:
            # Parse traffic data (handle different formats)
            if isinstance(traffic_data.get('roads'), str):
                roads = json.loads(traffic_data['roads'])
            else:
                roads = traffic_data.get('roads', {})
            
            # Calculate aggregate metrics
            total_vehicles = 0
            total_congestion = 0
            road_count = 0
            
            for road_name, road_data in roads.items():
                if isinstance(road_data, dict):
                    total_vehicles += road_data.get('vehicles', 0)
                    total_congestion += road_data.get('congestion', 0)
                    road_count += 1
            
            avg_congestion = total_congestion / max(road_count, 1)
            
            # Estimate revenue per hour
            revenue_per_hour = traffic_data.get('revenue', 0)
            if isinstance(revenue_per_hour, Decimal):
                revenue_per_hour = float(revenue_per_hour)
            
            return {
                'avg_congestion': avg_congestion,
                'total_vehicles': total_vehicles,
                'revenue_per_hour': revenue_per_hour,
                'roads': roads,
                'timestamp': traffic_data['timestamp']
            }
            
        except Exception as e:
            print(f"Error extracting state: {str(e)}")
            return {
                'avg_congestion': 0.5,
                'total_vehicles': 1000,
                'revenue_per_hour': 30000,
                'roads': {},
                'timestamp': datetime.now().isoformat()
            }
    
    def update_rl_model(self, episodes):
        """Update RL model with new episodes"""
        if not episodes:
            print("No episodes to train on")
            return False
        
        # Load existing model
        bucket_name = 'tai-lam-poc-models'
        self.rl_agent.load_model(bucket_name)
        
        # Train on new episodes
        for episode in episodes:
            # Calculate reward
            reward = self.rl_agent.calculate_reward(
                episode['state'],
                episode['next_state'],
                episode['action'],
                episode['toll_price']
            )
            
            # Update Q-table
            self.rl_agent.train_step(
                episode['state'],
                episode['action'],
                reward,
                episode['next_state']
            )
        
        # Save updated model
        success = self.rl_agent.save_model(bucket_name)
        
        if success:
            print(f"RL model updated with {len(episodes)} episodes")
            
            # Log model stats
            stats = self.rl_agent.get_model_stats()
            print(f"Model stats: {stats}")
        
        return success
    
    def retrain_supervised_model(self, traffic_data, toll_data):
        """Retrain supervised ML model with latest data"""
        try:
            # Prepare training data
            features = []
            targets = []
            
            for traffic, toll in zip(traffic_data, toll_data):
                state = self.extract_state(traffic)
                
                # Feature vector
                hour = datetime.fromisoformat(traffic['timestamp'].replace('Z', '+00:00')).hour
                feature_vector = [
                    hour,
                    hour / 24.0,  # normalized hour
                    state['avg_congestion'],
                    state['total_vehicles'] / 1000.0,  # normalized vehicles
                    1 if 7 <= hour <= 9 or 17 <= hour <= 19 else 0,  # rush hour
                    1 if hour >= 22 or hour <= 6 else 0  # night time
                ]
                
                features.append(feature_vector)
                targets.append(float(toll['toll_price']))
            
            if len(features) < 10:
                print("Insufficient data for retraining")
                return False
            
            # Train simple model (placeholder - would use scikit-learn in production)
            X = np.array(features)
            y = np.array(targets)
            
            # Simple linear regression coefficients
            coefficients = np.linalg.lstsq(X, y, rcond=None)[0]
            
            # Save updated model
            model_data = {
                'type': 'linear_regression',
                'coefficients': coefficients.tolist(),
                'timestamp': datetime.now().isoformat(),
                'training_samples': len(features)
            }
            
            bucket_name = 'tai-lam-poc-models'
            model_bytes = pickle.dumps(model_data)
            self.s3.put_object(
                Bucket=bucket_name,
                Key='updated_toll_model.pkl',
                Body=model_bytes
            )
            
            print(f"Supervised model retrained with {len(features)} samples")
            return True
            
        except Exception as e:
            print(f"Error retraining supervised model: {str(e)}")
            return False
    
    def run_model_update(self, hours_back=24):
        """Run complete model update process"""
        print(f"Starting model update with data from last {hours_back} hours...")
        
        # Get latest data
        traffic_data, toll_data = self.get_latest_data(hours_back)
        
        if not traffic_data or not toll_data:
            print("No new data available for training")
            return False
        
        print(f"Retrieved {len(traffic_data)} traffic records and {len(toll_data)} toll records")
        
        # Process training episodes
        episodes = self.process_training_data(traffic_data, toll_data)
        
        # Update RL model
        rl_success = self.update_rl_model(episodes)
        
        # Retrain supervised model
        supervised_success = self.retrain_supervised_model(traffic_data, toll_data)
        
        return rl_success and supervised_success

def lambda_model_updater(event, context):
    """Lambda function for scheduled model updates"""
    updater = ModelUpdater()
    
    # Get hours from event or default to 24
    hours_back = event.get('hours_back', 24)
    
    success = updater.run_model_update(hours_back)
    
    return {
        'statusCode': 200 if success else 500,
        'body': json.dumps({
            'success': success,
            'timestamp': datetime.now().isoformat(),
            'hours_processed': hours_back
        })
    }