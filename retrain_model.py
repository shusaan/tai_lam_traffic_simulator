"""Retrain ML model to fix version compatibility"""

import os
import sys
sys.path.append('src')

from ml_trainer import TollPricingMLModel

def retrain_model():
    """Retrain model with current scikit-learn version"""
    
    print("🔄 Retraining model to fix version compatibility...")
    
    # Remove old model
    if os.path.exists('models/toll_pricing_model.pkl'):
        os.remove('models/toll_pricing_model.pkl')
        print("🗑️ Removed old model")
    
    # Train new model
    ml_model = TollPricingMLModel()
    results = ml_model.train_model('hk_tunnel_traffic.csv')
    ml_model.save_model()
    
    print("✅ Model retrained successfully!")
    print(f"📊 Accuracy: {results['r2']:.1%}")
    print(f"📊 Error: HK${results['mae']:.2f}")

if __name__ == "__main__":
    retrain_model()