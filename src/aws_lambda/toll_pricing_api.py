"""AWS Lambda function for dynamic toll pricing API"""

import json
import boto3
import os
from datetime import datetime, timedelta
from decimal import Decimal
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
dynamodb = boto3.resource('dynamodb')
kinesis = boto3.client('kinesis')

# DynamoDB tables
traffic_table = dynamodb.Table(os.environ.get('TRAFFIC_TABLE', 'tai-lam-traffic-data'))
toll_table = dynamodb.Table(os.environ.get('TOLL_TABLE', 'tai-lam-toll-history'))

def lambda_handler(event, context):
    """Main Lambda handler for toll pricing API"""
    
    try:
        http_method = event.get('httpMethod', '')
        path = event.get('path', '')
        
        if http_method == 'GET' and path == '/toll/current':
            return get_current_toll(event, context)
        elif http_method == 'POST' and path == '/toll/update':
            return update_toll_price(event, context)
        elif http_method == 'GET' and path == '/toll/history':
            return get_toll_history(event, context)
        elif http_method == 'POST' and path == '/toll/calculate':
            return calculate_dynamic_toll(event, context)
        else:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Endpoint not found'})
            }
            
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Internal server error'})
        }

def get_current_toll(event, context):
    """Get current toll price"""
    try:
        # Get latest toll price from DynamoDB
        response = toll_table.scan(
            FilterExpression='attribute_exists(#ts)',
            ExpressionAttributeNames={'#ts': 'timestamp'},
            Limit=1,
            ScanIndexForward=False
        )
        
        if response['Items']:
            latest_toll = response['Items'][0]
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'current_toll': float(latest_toll['toll_price']),
                    'timestamp': latest_toll['timestamp'],
                    'valid_until': latest_toll.get('valid_until', ''),
                    'currency': 'HKD'
                })
            }
        else:
            # Return default toll if no data
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'current_toll': 8.0,
                    'timestamp': datetime.now().isoformat(),
                    'currency': 'HKD'
                })
            }
            
    except Exception as e:
        logger.error(f"Error getting current toll: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Failed to get current toll'})
        }

def update_toll_price(event, context):
    """Update toll price"""
    try:
        body = json.loads(event.get('body', '{}'))
        new_price = body.get('toll_price')
        reason = body.get('reason', 'Manual update')
        
        if not new_price or new_price < 5.0 or new_price > 25.0:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Invalid toll price. Must be between 5.0 and 25.0 HKD'})
            }
        
        timestamp = datetime.now().isoformat()
        valid_until = (datetime.now() + timedelta(minutes=15)).isoformat()
        
        # Store in DynamoDB
        toll_table.put_item(
            Item={
                'timestamp': timestamp,
                'toll_price': Decimal(str(new_price)),
                'valid_until': valid_until,
                'reason': reason,
                'updated_by': 'api'
            }
        )
        
        # Send to Kinesis for real-time processing
        kinesis.put_record(
            StreamName=os.environ.get('KINESIS_STREAM', 'tai-lam-traffic-stream'),
            Data=json.dumps({
                'event_type': 'toll_update',
                'timestamp': timestamp,
                'toll_price': new_price,
                'reason': reason
            }),
            PartitionKey='toll_updates'
        )
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'Toll price updated successfully',
                'new_price': new_price,
                'timestamp': timestamp,
                'valid_until': valid_until
            })
        }
        
    except Exception as e:
        logger.error(f"Error updating toll price: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Failed to update toll price'})
        }

def get_toll_history(event, context):
    """Get toll price history"""
    try:
        query_params = event.get('queryStringParameters', {}) or {}
        hours = int(query_params.get('hours', 24))
        
        # Calculate time range
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        
        # Query DynamoDB
        response = toll_table.scan(
            FilterExpression='#ts BETWEEN :start_time AND :end_time',
            ExpressionAttributeNames={'#ts': 'timestamp'},
            ExpressionAttributeValues={
                ':start_time': start_time.isoformat(),
                ':end_time': end_time.isoformat()
            }
        )
        
        # Convert Decimal to float for JSON serialization
        history = []
        for item in response['Items']:
            history.append({
                'timestamp': item['timestamp'],
                'toll_price': float(item['toll_price']),
                'reason': item.get('reason', ''),
                'updated_by': item.get('updated_by', '')
            })
        
        # Sort by timestamp
        history.sort(key=lambda x: x['timestamp'])
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'history': history,
                'count': len(history),
                'time_range_hours': hours
            })
        }
        
    except Exception as e:
        logger.error(f"Error getting toll history: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Failed to get toll history'})
        }

def calculate_dynamic_toll(event, context):
    """Calculate dynamic toll based on current traffic conditions"""
    try:
        body = json.loads(event.get('body', '{}'))
        
        # Get current traffic data
        traffic_data = get_latest_traffic_data()
        
        # Simple dynamic pricing algorithm
        tunnel_congestion = traffic_data.get('tunnel_congestion', 0.5)
        revenue_ratio = traffic_data.get('revenue_ratio', 1.0)
        time_of_day = datetime.now().hour
        
        # Base price
        base_price = 8.0
        
        # Congestion adjustment
        if tunnel_congestion > 0.8:
            congestion_multiplier = 1.5
        elif tunnel_congestion < 0.3:
            congestion_multiplier = 0.8
        else:
            congestion_multiplier = 1.0
        
        # Revenue adjustment
        if revenue_ratio < 0.7:
            revenue_multiplier = 1.2
        elif revenue_ratio > 1.3:
            revenue_multiplier = 0.9
        else:
            revenue_multiplier = 1.0
        
        # Time adjustment
        if 7 <= time_of_day <= 9 or 17 <= time_of_day <= 19:
            time_multiplier = 1.3
        elif 22 <= time_of_day <= 6:
            time_multiplier = 0.7
        else:
            time_multiplier = 1.0
        
        # Calculate new price
        new_price = base_price * congestion_multiplier * revenue_multiplier * time_multiplier
        new_price = max(5.0, min(25.0, new_price))  # Apply constraints
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'recommended_toll': round(new_price, 2),
                'factors': {
                    'congestion_multiplier': congestion_multiplier,
                    'revenue_multiplier': revenue_multiplier,
                    'time_multiplier': time_multiplier,
                    'tunnel_congestion': tunnel_congestion,
                    'revenue_ratio': revenue_ratio,
                    'time_of_day': time_of_day
                },
                'timestamp': datetime.now().isoformat()
            })
        }
        
    except Exception as e:
        logger.error(f"Error calculating dynamic toll: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Failed to calculate dynamic toll'})
        }

def get_latest_traffic_data():
    """Get latest traffic data from DynamoDB"""
    try:
        response = traffic_table.scan(
            Limit=1,
            ScanIndexForward=False
        )
        
        if response['Items']:
            return response['Items'][0]
        else:
            return {
                'tunnel_congestion': 0.5,
                'revenue_ratio': 1.0,
                'timestamp': datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error getting traffic data: {str(e)}")
        return {
            'tunnel_congestion': 0.5,
            'revenue_ratio': 1.0,
            'timestamp': datetime.now().isoformat()
        }