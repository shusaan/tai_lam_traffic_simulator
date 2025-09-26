"""Main entry point for Tai Lam Traffic Simulator"""

import argparse
import logging
import time
from datetime import datetime, timedelta

import sys
import os
sys.path.append('/app/src')
from simulator.traffic_simulator import TrafficSimulator
from simulator.simple_pricing_model import SimplePricingModel as HybridPricingModel
from simple_data_processor import TrafficDataProcessor, RealTimeDataStreamer
from config import SCENARIOS

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('traffic_simulator.log'),
            logging.StreamHandler()
        ]
    )

def run_simulation(scenario='normal', duration_hours=1, enable_aws=False):
    """Run traffic simulation"""
    logger = logging.getLogger(__name__)
    
    # Initialize components
    simulator = TrafficSimulator()
    pricing_model = HybridPricingModel()
    
    if enable_aws:
        data_processor = TrafficDataProcessor()
        streamer = RealTimeDataStreamer(data_processor)
    
    logger.info(f"Starting simulation with scenario: {scenario}")
    logger.info(f"Duration: {duration_hours} hours")
    
    prev_state = None
    simulation_data = []
    
    # Run simulation
    for minute in range(duration_hours * 60):
        # Simulate one minute
        traffic_snapshot = simulator.simulate_step(scenario)
        simulation_data.append(traffic_snapshot)
        
        # Update toll price every 15 minutes
        if minute % 15 == 0:
            current_state = simulator.get_current_state()
            new_toll = pricing_model.get_price_recommendation(current_state)
            simulator.update_toll_price(new_toll)
            
            logger.info(f"Minute {minute}: Toll updated to ${new_toll:.2f}")
            logger.info(f"Tunnel congestion: {current_state['tunnel_congestion']:.1%}")
            logger.info(f"Revenue: ${simulator.revenue:.2f}")
            
            # Train ML model
            if prev_state:
                pricing_model.train_step(prev_state, simulator.toll_price, current_state)
            
            prev_state = current_state
        
        # Stream to AWS if enabled
        if enable_aws:
            try:
                data_processor.simulate_traffic_stream(traffic_snapshot)
            except Exception as e:
                logger.warning(f"AWS streaming error: {e}")
        
        # Log progress every hour
        if minute % 60 == 0:
            logger.info(f"Hour {minute//60} completed")
    
    # Final results
    logger.info("Simulation completed!")
    logger.info(f"Final toll price: ${simulator.toll_price:.2f}")
    logger.info(f"Total revenue: ${simulator.revenue:.2f}")
    
    # Calculate performance metrics
    tunnel_congestion_avg = sum(d['roads']['tai_lam_tunnel']['congestion'] for d in simulation_data) / len(simulation_data)
    tmr_congestion_avg = sum(d['roads']['tuen_mun_road']['congestion'] for d in simulation_data) / len(simulation_data)
    nt_congestion_avg = sum(d['roads']['nt_circular_road']['congestion'] for d in simulation_data) / len(simulation_data)
    
    logger.info(f"Average congestion - Tunnel: {tunnel_congestion_avg:.1%}, TMR: {tmr_congestion_avg:.1%}, NT: {nt_congestion_avg:.1%}")
    
    return simulation_data

def run_dashboard():
    """Run web dashboard"""
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from dashboard.app import app
    print("Starting Tai Lam Traffic Simulator Dashboard...")
    print("Open http://localhost:8050 in your browser")
    app.run(debug=False, host='0.0.0.0', port=8050)

def test_aws_integration():
    """Test AWS integration"""
    logger = logging.getLogger(__name__)
    
    try:
        data_processor = TrafficDataProcessor()
        
        # Test data
        test_data = {
            'timestamp': datetime.now(),
            'scenario': 'test',
            'toll_price': 10.0,
            'revenue': 1000.0,
            'roads': {
                'tai_lam_tunnel': {'vehicles': 100, 'congestion': 0.5, 'travel_time': 5.0},
                'tuen_mun_road': {'vehicles': 200, 'congestion': 0.7, 'travel_time': 20.0},
                'nt_circular_road': {'vehicles': 150, 'congestion': 0.6, 'travel_time': 18.0}
            }
        }
        
        # Test Kinesis streaming
        data_processor.simulate_traffic_stream(test_data)
        logger.info("AWS Kinesis test successful")
        
        # Test DynamoDB storage
        data_processor.store_traffic_data_batch([test_data])
        logger.info("AWS DynamoDB test successful")
        
        # Test data retrieval
        historical_data = data_processor.get_historical_traffic_data(1)
        logger.info(f"Retrieved {len(historical_data)} historical records")
        
        logger.info("AWS integration test completed successfully")
        
    except Exception as e:
        logger.error(f"AWS integration test failed: {e}")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Tai Lam Traffic Simulator')
    parser.add_argument('--mode', choices=['simulate', 'dashboard', 'test-aws'], 
                       default='simulate', help='Run mode')
    parser.add_argument('--scenario', choices=list(SCENARIOS.keys()), 
                       default='normal', help='Traffic scenario')
    parser.add_argument('--duration', type=int, default=1, 
                       help='Simulation duration in hours')
    parser.add_argument('--enable-aws', action='store_true', 
                       help='Enable AWS integration')
    parser.add_argument('--verbose', action='store_true', 
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Setup logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    setup_logging()
    
    if args.mode == 'simulate':
        run_simulation(args.scenario, args.duration, args.enable_aws)
    elif args.mode == 'dashboard':
        run_dashboard()
    elif args.mode == 'test-aws':
        test_aws_integration()

if __name__ == '__main__':
    main()