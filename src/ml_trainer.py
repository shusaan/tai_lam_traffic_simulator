"""ML Model Training using Hong Kong historical traffic data"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, r2_score
import pickle
import os
from datetime import datetime
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import ROADS, TOLL_CONFIG, REVENUE_TARGET_HOURLY

class TollPricingMLModel:
    """ML model for dynamic toll pricing using historical HK data"""

    def __init__(self):
        self.model = RandomForestRegressor(n_estimators=100, random_state=42)
        self.scaler = StandardScaler()
        self.is_trained = False

    def load_and_prepare_data(self, csv_path='hk_tunnel_traffic.csv'):
        """Load and prepare Hong Kong traffic data"""
        print("📊 Loading Hong Kong traffic data...")

        # Load data
        df = pd.read_csv(csv_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # Extract time features
        df['hour'] = df['timestamp'].dt.hour
        df['day_of_week'] = df['timestamp'].dt.dayofweek
        df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)

        # Create congestion ratios (normalize by capacity from config)
        tai_lam_capacity = ROADS['tai_lam_tunnel'].capacity
        nt_capacity = ROADS['nt_circular_road'].capacity

        df['tai_lam_congestion'] = df['tai_lam'] / tai_lam_capacity
        df['nt_congestion'] = df['nt_circular'] / nt_capacity

        # Create peak indicators
        df['is_peak'] = (df['slot'] == 'peak').astype(int)
        df['is_morning_peak'] = ((df['hour'] >= 7) & (df['hour'] <= 9)).astype(int)
        df['is_evening_peak'] = ((df['hour'] >= 17) & (df['hour'] <= 19)).astype(int)

        print(f"✅ Loaded {len(df)} records from {df['timestamp'].min()} to {df['timestamp'].max()}")
        return df

    def create_optimal_toll_labels(self, df):
        """Create optimal toll price labels based on traffic patterns"""

        # Base toll price from config
        base_toll = TOLL_CONFIG.base_price
        max_toll = TOLL_CONFIG.max_price
        min_toll = TOLL_CONFIG.min_price

        # Calculate optimal toll based on congestion and demand
        optimal_toll = np.full(len(df), base_toll)

        # Increase toll during high congestion
        high_congestion = df['tai_lam_congestion'] > 0.8
        optimal_toll[high_congestion] = max_toll

        # Peak hour pricing
        peak_hours = df['is_peak'] == 1
        optimal_toll[peak_hours] = optimal_toll[peak_hours] * 1.5  # Peak multiplier

        # Weekend pricing (lower demand)
        weekend = df['is_weekend'] == 1
        optimal_toll[weekend] = optimal_toll[weekend] * 0.8  # Weekend discount

        # Night time pricing (very low demand)
        night_time = (df['hour'] >= 22) | (df['hour'] <= 5)
        optimal_toll[night_time] = min_toll

        # Apply constraints from config
        optimal_toll = np.clip(optimal_toll, TOLL_CONFIG.min_price, TOLL_CONFIG.max_price)

        return optimal_toll

    def prepare_features(self, df):
        """Prepare feature matrix for training"""

        features = [
            'tai_lam_congestion',
            'nt_congestion',
            'hour',
            'day_of_week',
            'is_weekend',
            'is_peak',
            'is_morning_peak',
            'is_evening_peak'
        ]

        X = df[features].copy()

        # Handle missing values
        X = X.fillna(X.mean())

        return X, features

    def train_model(self, csv_path='hk_tunnel_traffic.csv'):
        """Train the ML model on historical data"""

        # Load and prepare data
        df = self.load_and_prepare_data(csv_path)

        # Create optimal toll labels
        y = self.create_optimal_toll_labels(df)

        # Prepare features
        X, feature_names = self.prepare_features(df)

        print(f"📈 Training features: {feature_names}")
        print(f"🎯 Target range: HK${y.min():.2f} - HK${y.max():.2f}")

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, shuffle=True
        )

        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        # Train model
        print("🤖 Training Random Forest model...")
        self.model.fit(X_train_scaled, y_train)

        # Evaluate
        y_pred = self.model.predict(X_test_scaled)
        mae = mean_absolute_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)

        print(f"✅ Model trained successfully!")
        print(f"📊 Mean Absolute Error: HK${mae:.2f}")
        print(f"📊 R² Score: {r2:.3f}")

        # Feature importance
        importance = self.model.feature_importances_
        for name, imp in zip(feature_names, importance):
            print(f"   {name}: {imp:.3f}")

        self.is_trained = True
        self.feature_names = feature_names

        return {
            'mae': mae,
            'r2': r2,
            'feature_importance': dict(zip(feature_names, importance))
        }

    def predict_toll(self, traffic_state):
        """Predict optimal toll price for current traffic state"""

        if not self.is_trained:
            print("⚠️ Model not trained yet. Using default toll.")
            return 8.0

        # Prepare input features with proper column names
        import pandas as pd
        features_dict = {
            'tai_lam_congestion': [traffic_state.get('tunnel_congestion', 0.5)],
            'nt_congestion': [traffic_state.get('nt_congestion', 0.5)],
            'hour': [traffic_state.get('time_of_day', 12)],
            'day_of_week': [traffic_state.get('day_of_week', 1)],
            'is_weekend': [1 if traffic_state.get('day_of_week', 1) in [5, 6] else 0],
            'is_peak': [1 if traffic_state.get('is_peak', False) else 0],
            'is_morning_peak': [1 if 7 <= traffic_state.get('time_of_day', 12) <= 9 else 0],
            'is_evening_peak': [1 if 17 <= traffic_state.get('time_of_day', 12) <= 19 else 0]
        }
        features_df = pd.DataFrame(features_dict)
        features = features_df.values

        # Scale and predict
        features_scaled = self.scaler.transform(features)
        predicted_toll = self.model.predict(features_scaled)[0]

        # Apply constraints from config
        predicted_toll = np.clip(predicted_toll, TOLL_CONFIG.min_price, TOLL_CONFIG.max_price)

        return float(predicted_toll)

    def save_model(self, model_path='models/toll_pricing_model.pkl'):
        """Save trained model"""

        os.makedirs(os.path.dirname(model_path), exist_ok=True)

        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'feature_names': self.feature_names,
            'is_trained': self.is_trained,
            'trained_at': datetime.now().isoformat()
        }

        with open(model_path, 'wb') as f:
            pickle.dump(model_data, f)

        print(f"💾 Model saved to {model_path}")

    def load_model(self, model_path='models/toll_pricing_model.pkl'):
        """Load trained model"""

        if not os.path.exists(model_path):
            print(f"❌ Model file not found: {model_path}")
            return False

        with open(model_path, 'rb') as f:
            model_data = pickle.load(f)

        self.model = model_data['model']
        self.scaler = model_data['scaler']
        self.feature_names = model_data['feature_names']
        self.is_trained = model_data['is_trained']

        print(f"✅ Model loaded from {model_path}")
        print(f"📅 Trained at: {model_data['trained_at']}")

        return True

def main():
    """Train the model with Hong Kong data"""

    print("=== ML Model Training with Hong Kong Traffic Data ===")

    # Initialize model
    ml_model = TollPricingMLModel()

    # Train model
    results = ml_model.train_model('hk_tunnel_traffic.csv')

    # Save model
    ml_model.save_model()

    # Test prediction
    test_state = {
        'tunnel_congestion': 0.8,
        'nt_congestion': 0.6,
        'time_of_day': 8,
        'day_of_week': 1,
        'is_peak': True
    }

    predicted_toll = ml_model.predict_toll(test_state)
    print(f"\n🧪 Test Prediction:")
    print(f"   Rush hour (80% congestion) → HK${predicted_toll:.2f}")

    print(f"\n🎉 Training Complete!")
    print(f"   Model accuracy: {results['r2']:.1%}")
    print(f"   Average error: HK${results['mae']:.2f}")

if __name__ == "__main__":
    main()
