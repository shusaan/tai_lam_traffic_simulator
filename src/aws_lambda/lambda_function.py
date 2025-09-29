"""AI-powered Lambda function for toll pricing API"""

import json
import boto3
import os
import pickle
import numpy as np
from datetime import datetime
from decimal import Decimal
import sys
sys.path.append('/opt/python')

try:
    from rl_agent.q_learning_agent import QLearningTollAgent
    RL_AVAILABLE = True
except ImportError:
    RL_AVAILABLE = False
    print("RL agent not available, using fallback")

# Initialize AWS clients
s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

# Global variables for model caching
model = None
model_loaded = False

def load_model_from_s3():
    """Load ML model from S3 bucket"""
    global model, model_loaded
    
    if model_loaded:
        return model
    
    try:
        bucket_name = os.environ.get('MODEL_S3_BUCKET', 'tai-lam-poc-models')
        model_key = 'toll_pricing_model.pkl'
        
        # Download model from S3
        response = s3.get_object(Bucket=bucket_name, Key=model_key)
        model_data = response['Body'].read()
        
        # Load pickled model
        model = pickle.loads(model_data)
        model_loaded = True
        
        print(f"Model loaded successfully from s3://{bucket_name}/{model_key}")
        return model
        
    except Exception as e:
        print(f"Error loading model: {str(e)}")
        return None

def get_traffic_data():
    """Get latest traffic data from DynamoDB"""
    try:
        traffic_table_name = os.environ.get('TRAFFIC_TABLE', 'tai-lam-poc-traffic')
        table = dynamodb.Table(traffic_table_name)
        
        # Get latest traffic data
        response = table.scan(
            Limit=10,
            ScanIndexForward=False
        )
        
        if response['Items']:
            return response['Items'][0]
        else:
            # Return default traffic state
            return {
                'tai_lam_congestion': 0.6,
                'tuen_mun_congestion': 0.4,
                'nt_circular_congestion': 0.5,
                'total_vehicles': 1500,
                'timestamp': datetime.now().isoformat()
            }
            
    except Exception as e:
        print(f"Error getting traffic data: {str(e)}")
        return {
            'tai_lam_congestion': 0.6,
            'tuen_mun_congestion': 0.4,
            'nt_circular_congestion': 0.5,
            'total_vehicles': 1500,
            'timestamp': datetime.now().isoformat()
        }

def calculate_ai_toll_price(traffic_data):
    """Calculate toll price using AI model with RL integration"""
    try:
        # Try RL agent first
        if RL_AVAILABLE:
            rl_agent = QLearningTollAgent()
            bucket_name = os.environ.get('MODEL_S3_BUCKET', 'tai-lam-poc-models')
            
            if rl_agent.load_model(bucket_name):
                current_toll = 30.0  # Default current toll
                rl_toll, _ = rl_agent.get_toll_recommendation(traffic_data, current_toll)
                return float(rl_toll)
        
        # Fallback to supervised ML model
        model = load_model_from_s3()
        
        if model is None:
            return calculate_rule_based_toll(traffic_data)
        
        # Prepare features for ML model
        current_time = datetime.now()
        hour = current_time.hour
        minute = current_time.minute
        
        # Feature engineering (same as training)
        features = np.array([[
            hour,  # hour of day
            minute / 60.0,  # fraction of hour
            traffic_data.get('tai_lam_congestion', 0.6),
            traffic_data.get('tuen_mun_congestion', 0.4),
            traffic_data.get('nt_circular_congestion', 0.5),
            traffic_data.get('total_vehicles', 1500) / 1000.0,  # normalized
            1 if 7 <= hour <= 9 or 17 <= hour <= 19 else 0,  # rush hour
            1 if hour >= 22 or hour <= 6 else 0  # night time
        ]])
        
        # Get AI prediction
        predicted_toll = model.predict(features)[0]
        
        # Ensure toll is within bounds
        min_toll, max_toll = 18.0, 55.0
        predicted_toll = max(min_toll, min(max_toll, predicted_toll))
        
        return float(predicted_toll)
        
    except Exception as e:
        print(f"Error in AI prediction: {str(e)}")
        return calculate_rule_based_toll(traffic_data)

def calculate_rule_based_toll(traffic_data):
    """Fallback rule-based toll calculation"""
    base_toll = 30.0
    congestion_factor = traffic_data.get('tai_lam_congestion', 0.6)
    
    # Adjust based on congestion
    if congestion_factor > 0.8:
        toll_multiplier = 1.5  # High congestion
    elif congestion_factor > 0.5:
        toll_multiplier = 1.2  # Medium congestion
    else:
        toll_multiplier = 0.9  # Low congestion
    
    # Time-based adjustment
    current_hour = datetime.now().hour
    if 7 <= current_hour <= 9 or 17 <= current_hour <= 19:
        toll_multiplier *= 1.3  # Rush hour premium
    
    calculated_toll = base_toll * toll_multiplier
    return max(18.0, min(55.0, calculated_toll))

def lambda_handler(event, context):
    """Main Lambda handler with AI toll pricing"""
    
    try:
        # Handle different HTTP methods
        http_method = event.get('httpMethod', 'GET')
        
        if http_method == 'GET':
            return get_ai_toll_price()
        elif http_method == 'POST':
            return calculate_toll_recommendation(event)
        else:
            return {
                'statusCode': 405,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Method not allowed'})
            }
            
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }

def get_ai_toll_price():
    """Get AI-calculated toll price"""
    
    try:
        # Get current traffic data
        traffic_data = get_traffic_data()
        
        # Calculate AI toll price
        ai_toll_price = calculate_ai_toll_price(traffic_data)
        
        # Store in DynamoDB
        toll_table_name = os.environ.get('TOLL_TABLE', 'tai-lam-poc-tolls')
        table = dynamodb.Table(toll_table_name)
        
        table.put_item(
            Item={
                'timestamp': datetime.now().isoformat(),
                'toll_price': Decimal(str(ai_toll_price)),
                'source': 'ai_model',
                'traffic_data': traffic_data
            }
        )
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'toll_price': ai_toll_price,
                'currency': 'HKD',
                'timestamp': datetime.now().isoformat(),
                'source': 'ai_model',
                'traffic_congestion': {
                    'tai_lam': traffic_data.get('tai_lam_congestion', 0.6),
                    'tuen_mun': traffic_data.get('tuen_mun_congestion', 0.4),
                    'nt_circular': traffic_data.get('nt_circular_congestion', 0.5)
                },
                'status': 'success'
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': f'AI calculation error: {str(e)}',
                'toll_price': 30.0,  # Fallback
                'currency': 'HKD',
                'source': 'fallback'
            })
        }

def calculate_toll_recommendation(event):
    """Calculate toll recommendation based on POST data"""
    
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        
        # Use provided traffic data or get current
        if 'traffic_data' in body:
            traffic_data = body['traffic_data']
        else:
            traffic_data = get_traffic_data()
        
        # Calculate recommendation
        recommended_toll = calculate_ai_toll_price(traffic_data)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'recommended_toll': recommended_toll,
                'currency': 'HKD',
                'timestamp': datetime.now().isoformat(),
                'input_data': traffic_data,
                'source': 'ai_recommendation'
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': f'Request processing error: {str(e)}'
            })
        }