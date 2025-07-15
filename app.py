#!/usr/bin/env python3
"""
Ushauri AI: Kenya Health Intelligence System
Entry point for Hugging Face Spaces deployment
"""

import os
import sys
from pathlib import Path
import shutil

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set demo mode for Hugging Face Spaces
os.environ['DEMO_MODE'] = 'true'
os.environ['USE_SAMPLE_DATA'] = 'true'

# Copy demo environment file if .env doesn't exist
env_file = project_root / '.env'
demo_env_file = project_root / '.env.demo'

if not env_file.exists() and demo_env_file.exists():
    shutil.copy(demo_env_file, env_file)
    print("✅ Demo environment configuration loaded")

# Set environment variables for Hugging Face Spaces
os.environ.setdefault('STREAMLIT_SERVER_HEADLESS', 'true')
os.environ.setdefault('STREAMLIT_SERVER_PORT', '7860')
os.environ.setdefault('STREAMLIT_SERVER_ADDRESS', '0.0.0.0')
os.environ.setdefault('STREAMLIT_BROWSER_GATHER_USAGE_STATS', 'false')

# Patch database imports for demo mode
def patch_db_imports():
    """Replace database imports with demo versions"""
    try:
        # Replace db module with demo_db
        import tools.demo_db as demo_db
        sys.modules['tools.db'] = demo_db
        print("✅ Demo database module loaded")
    except ImportError as e:
        print(f"⚠️ Could not load demo database: {e}")

# Apply patches
patch_db_imports()

# Import and run the main Streamlit app
if __name__ == "__main__":
    import subprocess
    import sys

    print("🚀 Starting Ushauri AI - Kenya Health Intelligence System")
    print("🎯 Demo Mode: Using sample data for demonstration")

    # Run the Streamlit app
    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        "app/main_streamlit_app.py",
        "--server.port=7860",
        "--server.address=0.0.0.0",
        "--server.headless=true",
        "--browser.gatherUsageStats=false"
    ])
