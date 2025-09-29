"""Data processor for Hong Kong traffic data and AWS integration"""

import boto3
import json
import pandas as pd
import xmltodict
import requests
from datetime import datetime, timedelta
from typing import Dict, List
import logging

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import AWS_REGION, DYNAMODB_TABLE_TRAFFIC, KINESIS_STREAM

class TrafficDataProcessor:
    """Process and stream traffic data to AWS services"""
    
    def __init__(self):
        self.kinesis_client = boto3.client('kinesis', region_name=AWS_REGION)
        self.dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
        self.traffic_table = self.dynamodb.Table(DYNAMODB_TABLE_TRAFFIC)
        self.logger = logging.getLogger(__name__)
        
    def parse_hk_traffic_xml(self, xml_file_path: str) -> pd.DataFrame:
        """Parse Hong Kong traffic XML data"""
        try:
            with open(xml_file_path, 'r', encoding='utf-8') as file:
                xml_content = file.read()
            
            # Parse XML to dictionary
            data_dict = xmltodict.parse(xml_content)
            
            # Extract traffic detector data
            detectors = data_dict.get('traffic_detectors', {}).get('detector', [])
            
            traffic_data = []
            for detector in detectors:
                if isinstance(detector, dict):
                    traffic_data.append({
                        'detector_id': detector.get('@id', ''),
                        'location': detector.get('@location', ''),
                        'speed': float(detector.get('speed', 0)),
                        'volume': int(detector.get('volume', 0)),
                        'occupancy': float(detector.get('occupancy', 0)),
                        'timestamp': detector.get('@timestamp', datetime.now().isoformat())
                    })
            
            return pd.DataFrame(traffic_data)
            
        except Exception as e:
            self.logger.error(f"Error parsing XML file: {str(e)}")
            return pd.DataFrame()
    
    def filter_tai_lam_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Filter data for Tai Lam Tunnel area"""
        # Filter for relevant locations (adjust based on actual detector IDs)
        tai_lam_keywords = ['tai lam', 'tuen mun', 'tsuen wan', 'nt circular']
        
        filtered_df = df[
            df['location'].str.lower().str.contains('|'.join(tai_lam_keywords), na=False)
        ]
        
        return filtered_df
    
    def simulate_traffic_stream(self, simulation_data: Dict):
        """Send simulation data to Kinesis stream"""
        try:
            # Prepare traffic event
            traffic_event = {
                'event_type': 'traffic_update',
                'timestamp': simulation_data['timestamp'].isoformat(),
                'tunnel_vehicles': simulation_data['roads']['tai_lam_tunnel']['vehicles'],
                'tunnel_congestion': simulation_data['roads']['tai_lam_tunnel']['congestion'],
                'tunnel_travel_time': simulation_data['roads']['tai_lam_tunnel']['travel_time'],
                'tmr_vehicles': simulation_data['roads']['tuen_mun_road']['vehicles'],
                'tmr_congestion': simulation_data['roads']['tuen_mun_road']['congestion'],
                'tmr_travel_time': simulation_data['roads']['tuen_mun_road']['travel_time'],
                'nt_vehicles': simulation_data['roads']['nt_circular_road']['vehicles'],
                'nt_congestion': simulation_data['roads']['nt_circular_road']['congestion'],
                'nt_travel_time': simulation_data['roads']['nt_circular_road']['travel_time'],
                'total_revenue': simulation_data['revenue'],
                'current_toll': simulation_data['toll_price'],
                'scenario': simulation_data['scenario']
            }
            
            # Send to Kinesis
            response = self.kinesis_client.put_record(
                StreamName=KINESIS_STREAM,
                Data=json.dumps(traffic_event),
                PartitionKey=f"traffic_{datetime.now().strftime('%Y%m%d%H')}"
            )
            
            self.logger.info(f"Sent traffic data to Kinesis: {response['SequenceNumber']}")
            
        except Exception as e:
            self.logger.error(f"Error sending to Kinesis: {str(e)}")
    
    def store_traffic_data_batch(self, traffic_data_list: List[Dict]):
        """Store multiple traffic records in DynamoDB"""
        try:
            with self.traffic_table.batch_writer() as batch:
                for data in traffic_data_list:
                    # Convert timestamp to string if it's datetime
                    if isinstance(data.get('timestamp'), datetime):
                        data['timestamp'] = data['timestamp'].isoformat()
                    
                    batch.put_item(Item=data)
            
            self.logger.info(f"Stored {len(traffic_data_list)} traffic records")
            
        except Exception as e:
            self.logger.error(f"Error storing traffic data: {str(e)}")
    
    def get_historical_traffic_data(self, hours: int = 24) -> List[Dict]:
        """Retrieve historical traffic data from DynamoDB"""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours)
            
            response = self.traffic_table.scan(
                FilterExpression='#ts BETWEEN :start_time AND :end_time',
                ExpressionAttributeNames={'#ts': 'timestamp'},
                ExpressionAttributeValues={
                    ':start_time': start_time.isoformat(),
                    ':end_time': end_time.isoformat()
                }
            )
            
            return response['Items']
            
        except Exception as e:
            self.logger.error(f"Error retrieving historical data: {str(e)}")
            return []
    
    def calculate_traffic_metrics(self, traffic_data: List[Dict]) -> Dict:
        """Calculate traffic performance metrics"""
        if not traffic_data:
            return {}
        
        df = pd.DataFrame(traffic_data)
        
        # Convert numeric columns
        numeric_cols = ['tunnel_congestion', 'tmr_congestion', 'nt_congestion', 
                       'tunnel_travel_time', 'tmr_travel_time', 'nt_travel_time',
                       'total_revenue', 'current_toll']
        
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        metrics = {
            'avg_tunnel_congestion': df['tunnel_congestion'].mean() if 'tunnel_congestion' in df.columns else 0,
            'avg_tmr_congestion': df['tmr_congestion'].mean() if 'tmr_congestion' in df.columns else 0,
            'avg_nt_congestion': df['nt_congestion'].mean() if 'nt_congestion' in df.columns else 0,
            'avg_tunnel_travel_time': df['tunnel_travel_time'].mean() if 'tunnel_travel_time' in df.columns else 0,
            'total_revenue': df['total_revenue'].sum() if 'total_revenue' in df.columns else 0,
            'avg_toll_price': df['current_toll'].mean() if 'current_toll' in df.columns else 0,
            'peak_congestion_time': self._find_peak_congestion_time(df),
            'revenue_per_hour': df['total_revenue'].sum() / max(1, len(df) / 60) if 'total_revenue' in df.columns else 0
        }
        
        return metrics
    
    def _find_peak_congestion_time(self, df: pd.DataFrame) -> str:
        """Find the time with highest average congestion"""
        try:
            if 'timestamp' not in df.columns:
                return "Unknown"
            
            df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
            
            congestion_cols = ['tunnel_congestion', 'tmr_congestion', 'nt_congestion']
            available_cols = [col for col in congestion_cols if col in df.columns]
            
            if not available_cols:
                return "Unknown"
            
            df['avg_congestion'] = df[available_cols].mean(axis=1)
            peak_hour = df.groupby('hour')['avg_congestion'].mean().idxmax()
            
            return f"{peak_hour:02d}:00"
            
        except Exception:
            return "Unknown"

class RealTimeDataStreamer:
    """Stream real-time traffic data simulation"""
    
    def __init__(self, data_processor: TrafficDataProcessor):
        self.data_processor = data_processor
        self.is_streaming = False
        
    def start_streaming(self, simulator, scenario: str = "normal", duration_minutes: int = 60):
        """Start streaming simulation data"""
        self.is_streaming = True
        
        for minute in range(duration_minutes):
            if not self.is_streaming:
                break
                
            # Run simulation step
            traffic_snapshot = simulator.simulate_step(scenario)
            
            # Stream to AWS
            self.data_processor.simulate_traffic_stream(traffic_snapshot)
            
            # Wait for next minute (in real implementation, use proper timing)
            # time.sleep(60)  # Uncomment for real-time streaming
            
        self.is_streaming = False
    
    def stop_streaming(self):
        """Stop streaming"""
        self.is_streaming = False