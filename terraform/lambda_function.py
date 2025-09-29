import json
import boto3
import os
from decimal import Decimal

def lambda_handler(event, context):
    """
    Simple Lambda function for toll pricing API
    """
    
    # Get DynamoDB table names from environment
    traffic_table = os.environ.get('TRAFFIC_TABLE', 'tai-lam-poc-traffic')
    toll_table = os.environ.get('TOLL_TABLE', 'tai-lam-poc-tolls')
    
    # Initialize DynamoDB client
    dynamodb = boto3.resource('dynamodb')
    
    try:
        # Simple toll calculation logic
        current_toll = Decimal('30.00')  # Base toll price
        
        # Return current toll price
        response = {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'toll_price': float(current_toll),
                'currency': 'HKD',
                'timestamp': context.aws_request_id
            })
        }
        
        return response
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': str(e)
            })
        }