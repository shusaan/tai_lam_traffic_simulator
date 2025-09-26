"""Deployment script for Tai Lam Traffic Simulator"""

import os
import subprocess
import zipfile
import shutil
import boto3
from pathlib import Path

def create_lambda_package(function_name, source_file):
    """Create Lambda deployment package"""
    print(f"Creating Lambda package for {function_name}...")
    
    # Create temporary directory
    temp_dir = f"temp_{function_name}"
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # Copy source file
        shutil.copy(f"src/aws_lambda/{source_file}", f"{temp_dir}/{source_file}")
        
        # Install dependencies
        subprocess.run([
            "pip", "install", "-r", "requirements.txt", 
            "-t", temp_dir, "--no-deps"
        ], check=True)
        
        # Create zip file
        zip_filename = f"{function_name}.zip"
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, temp_dir)
                    zipf.write(file_path, arcname)
        
        print(f"Created {zip_filename}")
        return zip_filename
        
    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

def deploy_infrastructure():
    """Deploy AWS infrastructure using Terraform"""
    print("Deploying AWS infrastructure...")
    
    os.chdir("terraform")
    
    try:
        # Initialize Terraform
        subprocess.run(["terraform", "init"], check=True)
        
        # Plan deployment
        subprocess.run(["terraform", "plan"], check=True)
        
        # Apply deployment
        result = subprocess.run(["terraform", "apply", "-auto-approve"], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print("Infrastructure deployed successfully!")
            
            # Extract outputs
            output_result = subprocess.run(["terraform", "output", "-json"], 
                                         capture_output=True, text=True)
            if output_result.returncode == 0:
                import json
                outputs = json.loads(output_result.stdout)
                
                print("\nDeployment Outputs:")
                for key, value in outputs.items():
                    print(f"  {key}: {value['value']}")
                
                # Save outputs to file
                with open("../deployment_outputs.json", "w") as f:
                    json.dump(outputs, f, indent=2)
                    
        else:
            print(f"Infrastructure deployment failed: {result.stderr}")
            
    finally:
        os.chdir("..")

def update_lambda_functions():
    """Update Lambda function code"""
    print("Updating Lambda functions...")
    
    # Create Lambda packages
    toll_pricing_zip = create_lambda_package("toll_pricing_api", "toll_pricing_api.py")
    traffic_ingestion_zip = create_lambda_package("traffic_ingestion", "traffic_ingestion.py")
    
    # Move zip files to terraform directory
    shutil.move(toll_pricing_zip, f"terraform/{toll_pricing_zip}")
    shutil.move(traffic_ingestion_zip, f"terraform/{traffic_ingestion_zip}")
    
    print("Lambda packages created and moved to terraform directory")

def setup_local_environment():
    """Setup local development environment"""
    print("Setting up local environment...")
    
    # Install Python dependencies
    subprocess.run(["pip", "install", "-r", "requirements.txt"], check=True)
    
    # Create necessary directories
    os.makedirs("logs", exist_ok=True)
    os.makedirs("data", exist_ok=True)
    os.makedirs("models", exist_ok=True)
    
    print("Local environment setup complete!")

def run_tests():
    """Run basic tests"""
    print("Running tests...")
    
    try:
        # Test imports
        from src.simulator.traffic_simulator import TrafficSimulator
        from src.simulator.ml_pricing_model import HybridPricingModel
        from src.config import ROADS, SCENARIOS
        
        # Basic functionality test
        simulator = TrafficSimulator()
        pricing_model = HybridPricingModel()
        
        # Run a few simulation steps
        for i in range(5):
            snapshot = simulator.simulate_step("normal")
            state = simulator.get_current_state()
            new_toll = pricing_model.get_price_recommendation(state)
            simulator.update_toll_price(new_toll)
        
        print("✓ Core simulation functionality working")
        
        # Test configuration
        assert len(ROADS) == 3
        assert len(SCENARIOS) == 4
        print("✓ Configuration loaded correctly")
        
        print("All tests passed!")
        
    except Exception as e:
        print(f"✗ Tests failed: {e}")
        return False
    
    return True

def main():
    """Main deployment function"""
    print("=== Tai Lam Traffic Simulator Deployment ===")
    
    # Check if we're in the right directory
    if not os.path.exists("src") or not os.path.exists("requirements.txt"):
        print("Error: Please run this script from the project root directory")
        return
    
    try:
        # Setup local environment
        setup_local_environment()
        
        # Run tests
        if not run_tests():
            print("Tests failed. Aborting deployment.")
            return
        
        # Create Lambda packages
        update_lambda_functions()
        
        # Deploy infrastructure
        deploy_infrastructure()
        
        print("\n=== Deployment Complete ===")
        print("Next steps:")
        print("1. Run 'python src/main.py --mode dashboard' to start the web interface")
        print("2. Run 'python src/main.py --mode simulate --scenario rush_hour --enable-aws' to test AWS integration")
        print("3. Check deployment_outputs.json for AWS resource details")
        
    except subprocess.CalledProcessError as e:
        print(f"Deployment failed: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()