"""Production model management with S3 storage"""

import os
import boto3
import pickle
from datetime import datetime
import logging

class ProductionModelManager:
    """Manages ML models in production with S3 storage"""
    
    def __init__(self):
        self.s3_bucket = os.getenv('MODEL_S3_BUCKET', 'tai-lam-models')
        self.model_key = 'toll_pricing_model.pkl'
        self.local_model_path = 'models/toll_pricing_model.pkl'
        self.s3_client = None
        
        # Initialize S3 client if credentials available
        try:
            self.s3_client = boto3.client('s3')
            logging.info("✅ S3 client initialized")
        except Exception as e:
            logging.warning(f"⚠️ S3 not available: {e}")
    
    def download_latest_model(self):
        """Download latest model from S3"""
        if not self.s3_client:
            logging.info("📁 No S3 access, using local model if available")
            return os.path.exists(self.local_model_path)
        
        try:
            # Check if model exists in S3
            self.s3_client.head_object(Bucket=self.s3_bucket, Key=self.model_key)
            
            # Download model
            os.makedirs(os.path.dirname(self.local_model_path), exist_ok=True)
            self.s3_client.download_file(
                self.s3_bucket, 
                self.model_key, 
                self.local_model_path
            )
            
            logging.info("✅ Downloaded latest model from S3")
            return True
            
        except Exception as e:
            logging.warning(f"⚠️ Model download failed: {e}")
            return False
    
    def upload_trained_model(self, model_data):
        """Upload newly trained model to S3"""
        if not self.s3_client:
            logging.warning("⚠️ Cannot upload model - no S3 access")
            return False
        
        try:
            # Save model locally first
            os.makedirs(os.path.dirname(self.local_model_path), exist_ok=True)
            with open(self.local_model_path, 'wb') as f:
                pickle.dump(model_data, f)
            
            # Upload to S3
            self.s3_client.upload_file(
                self.local_model_path,
                self.s3_bucket,
                self.model_key
            )
            
            # Add metadata
            self.s3_client.put_object_tagging(
                Bucket=self.s3_bucket,
                Key=self.model_key,
                Tagging={
                    'TagSet': [
                        {'Key': 'UpdatedAt', 'Value': datetime.now().isoformat()},
                        {'Key': 'Environment', 'Value': 'production'}
                    ]
                }
            )
            
            logging.info("✅ Model uploaded to S3")
            return True
            
        except Exception as e:
            logging.error(f"❌ Model upload failed: {e}")
            return False
    
    def get_model_info(self):
        """Get model metadata"""
        if not self.s3_client:
            return {"source": "local", "last_updated": "unknown"}
        
        try:
            response = self.s3_client.head_object(
                Bucket=self.s3_bucket, 
                Key=self.model_key
            )
            
            return {
                "source": "s3",
                "last_updated": response['LastModified'].isoformat(),
                "size": response['ContentLength']
            }
            
        except Exception:
            return {"source": "none", "last_updated": "never"}

# Global model manager instance
model_manager = ProductionModelManager()