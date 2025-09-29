"""Simple Lambda function for toll pricing API (Free Tier optimized)"""

import json
import boto3
import os
from datetime import datetime
from decimal import Decimal

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb')

def lambda_handler(event, context):
    """Main Lambda handler - optimized for free tier"""
    
    try:
        # Get table names from environment
        toll_table_name = os.environ.get('TOLL_TABLE', 'tai-lam-poc-tolls')
        
        # Simple GET toll price endpoint
        if event.get('httpMethod') == 'GET':
            return get_current_toll(toll_table_name)
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

def get_current_toll(table_name):
    """Get current toll price from DynamoDB"""
    
    try:
        table = dynamodb.Table(table_name)
        
        # Try to get latest toll price
        response = table.scan(
            Limit=1,
            ScanIndexForward=False
        )
        
        if response['Items']:
            latest_toll = response['Items'][0]
            toll_price = float(latest_toll.get('toll_price', 8.0))
        else:
            # Default toll price
            toll_price = 8.0
            
            # Store default in DynamoDB
            table.put_item(
                Item={
                    'timestamp': datetime.now().isoformat(),
                    'toll_price': Decimal('8.0'),
                    'source': 'default'
                }
            )
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'toll_price': toll_price,
                'currency': 'HKD',
                'timestamp': datetime.now().isoformat(),
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
                'error': f'Database error: {str(e)}',
                'toll_price': 8.0,  # Fallback
                'currency': 'HKD'
            })
        }