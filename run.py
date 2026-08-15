import os
import sys
import subprocess
import time

def check_dependencies():
    print("Checking database and model assets...")
    
    # 1. Ensure directories exist
    os.makedirs("models", exist_ok=True)
    os.makedirs("data/raw", exist_ok=True)
    os.makedirs("data/processed", exist_ok=True)
    os.makedirs("data/synthetic", exist_ok=True)
    
    # 2. Check if .env exists
    if not os.path.exists(".env"):
        print(".env file not found. Copying .env.example...")
        if os.path.exists(".env.example"):
            with open(".env.example", "r") as f_ex, open(".env", "w") as f_env:
                f_env.write(f_ex.read())
        else:
            with open(".env", "w") as f_env:
                f_env.write("DATABASE_URL=sqlite:///./medcare_pharma.db\n")

    # 3. Check if synthetic data needs to be generated
    if not os.path.exists("data/raw/demand_history.csv"):
        print("Raw demand history data missing. Generating synthetic data...")
        subprocess.run([sys.executable, "scripts/generate_data.py"], check=True)
        
    # 4. Check if forecasting model needs to be trained
    if not os.path.exists("models/xgb_model_7d.pkl"):
        print("Trained model files missing. Running model training pipeline...")
        subprocess.run([sys.executable, "scripts/train_model.py"], check=True)
        
    # 5. Check if SQLite database exists and is populated
    # If SQLite database file is missing, seed it
    db_file = "medcare_pharma.db"
    if not os.path.exists(db_file):
        print("Database file missing. Seeding database...")
        subprocess.run([sys.executable, "scripts/seed_database.py"], check=True)
        
    # Generate initial forecasts and recommendations in the database for current date 2026-08-12
    # We will invoke our forecast/recommendation seeder to ensure database starts with data
    # print("Pre-seeding initial forecasts and action recommendations in database...")
    # subprocess.run([sys.executable, "scripts/run_demo.py", "--init"], check=True)
    
    print("All assets verified and ready!")

def run_all():
    check_dependencies()
    
    port = os.environ.get("PORT", "8000")
    print(f"Starting FastAPI Backend & Web Dashboard on http://0.0.0.0:{port}...")
    
    try:
        # Run FastAPI in the foreground directly
        subprocess.run(
            [sys.executable, "-m", "uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", port],
            check=True
        )
    except KeyboardInterrupt:
        print("\nTerminating services...")
    finally:
        print("Services stopped.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--check-only":
        check_dependencies()
    else:
        run_all()
