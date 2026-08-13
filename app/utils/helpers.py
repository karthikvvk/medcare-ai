import os
import sys
from datetime import date, timedelta

def get_date_range(start_date: date, end_date: date):
    """Generates dates sequentially between start_date and end_date."""
    for n in range(int((end_date - start_date).days) + 1):
        yield start_date + timedelta(n)

def check_env_file():
    """Checks if .env file exists and has minimum required values."""
    if not os.path.exists(".env"):
        if os.path.exists(".env.example"):
            import shutil
            shutil.copy(".env.example", ".env")
            print("Created .env from .env.example")
            return True
        return False
    return True
