"""Production build script - trains model with correct versions"""

import subprocess
import os

def build_production():
    """Build production-ready model and container"""
    
    print("🏭 Building Production Version...")
    
    # Step 1: Train model locally with correct versions
    print("1️⃣ Training ML model...")
    try:
        subprocess.run(["python", "retrain_model.py"], check=True)
        print("✅ Model trained successfully")
    except subprocess.CalledProcessError:
        print("⚠️ Model training failed, will use fallback rules")
    
    # Step 2: Build Docker image
    print("2️⃣ Building Docker image...")
    subprocess.run([
        "docker", "build", 
        "-f", "Dockerfile.minimal",
        "-t", "tai-lam-traffic:production",
        "."
    ], check=True)
    
    # Step 3: Test container
    print("3️⃣ Testing container...")
    result = subprocess.run([
        "docker", "run", "--rm", "-d", 
        "--name", "test-container",
        "-p", "8051:8050",
        "tai-lam-traffic:production"
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Container started successfully")
        print("🌐 Test at: http://localhost:8051")
        print("🛑 Stop with: docker stop test-container")
    else:
        print("❌ Container failed to start")
    
    print("\n🎉 Production build complete!")
    print("📦 Image: tai-lam-traffic:production")

if __name__ == "__main__":
    build_production()