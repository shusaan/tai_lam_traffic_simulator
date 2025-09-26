"""AWS Lambda function for traffic data ingestion from Kinesis"""

import json
import boto3
import base64
from datetime import datetime
from decimal import Decimal
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
dynamodb = boto3.resource('dynamodb')
traffic_table = dynamodb.Table('tai-lam-traffic-data')

def lambda_handler(event, context):
    """Process traffic data from Kinesis stream"""
    
    processed_records = 0
    failed_records = 0
    
    try:
        for record in event['Records']:
            try:
                # Decode Kinesis data
                payload = base64.b64decode(record['kinesis']['data'])
                data = json.loads(payload.decode('utf-8'))
                
                # Process the traffic data
                process_traffic_record(data)
                processed_records += 1
                
            except Exception as e:
                logger.error(f"Error processing record: {str(e)}")
                failed_records += 1
                continue
        
        logger.info(f"Processed {processed_records} records, {failed_records} failed")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'processed': processed_records,
                'failed': failed_records
            })
        }
        
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Processing failed'})
        }

def process_traffic_record(data):
    """Process individual traffic record"""
    
    event_type = data.get('event_type', 'traffic_update')
    timestamp = data.get('timestamp', datetime.now().isoformat())
    
    if event_type == 'traffic_update':
        # Store traffic data
        item = {
            'timestamp': timestamp,
            'event_type': event_type,
            'tunnel_vehicles': convert_to_decimal(data.get('tunnel_vehicles', 0)),
            'tunnel_congestion': convert_to_decimal(data.get('tunnel_congestion', 0)),
            'tunnel_travel_time': convert_to_decimal(data.get('tunnel_travel_time', 0)),
            'tmr_vehicles': convert_to_decimal(data.get('tmr_vehicles', 0)),
            'tmr_congestion': convert_to_decimal(data.get('tmr_congestion', 0)),
            'tmr_travel_time': convert_to_decimal(data.get('tmr_travel_time', 0)),
            'nt_vehicles': convert_to_decimal(data.get('nt_vehicles', 0)),
            'nt_congestion': convert_to_decimal(data.get('nt_congestion', 0)),
            'nt_travel_time': convert_to_decimal(data.get('nt_travel_time', 0)),
            'total_revenue': convert_to_decimal(data.get('total_revenue', 0)),
            'current_toll': convert_to_decimal(data.get('current_toll', 8.0)),
            'scenario': data.get('scenario', 'normal')
        }
        
        traffic_table.put_item(Item=item)
        logger.info(f"Stored traffic data for timestamp: {timestamp}")
        
    elif event_type == 'toll_update':
        # Handle toll update events
        logger.info(f"Toll updated to {data.get('toll_price')} at {timestamp}")
        
    elif event_type == 'scenario_change':
        # Handle scenario change events
        logger.info(f"Scenario changed to {data.get('scenario')} at {timestamp}")

def convert_to_decimal(value):
    """Convert numeric value to Decimal for DynamoDB"""
    if value is None:
        return Decimal('0')
    return Decimal(str(value))

def batch_write_traffic_data(records):
    """Batch write multiple traffic records"""
    
    try:
        with traffic_table.batch_writer() as batch:
            for record in records:
                batch.put_item(Item=record)
        
        logger.info(f"Batch wrote {len(records)} traffic records")
        
    except Exception as e:
        logger.error(f"Error in batch write: {str(e)}")
        raise