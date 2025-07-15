#!/usr/bin/env python3
"""
Launch script for Ushauri AI Performance Monitoring Dashboard
Kenya Community Health Systems
"""

import subprocess
import sys
import os
from pathlib import Path

def main():
    """Launch the monitoring dashboard"""
    
    # Get the directory of this script
    script_dir = Path(__file__).parent
    dashboard_path = script_dir / "monitoring" / "dashboard.py"
    
    # Check if dashboard file exists
    if not dashboard_path.exists():
        print(f"❌ Dashboard file not found: {dashboard_path}")
        return 1
    
    print("🚀 Launching Ushauri AI Performance Monitoring Dashboard...")
    print("🏥 Kenya Community Health Systems")
    print(f"📊 Dashboard location: {dashboard_path}")
    print("🌐 The dashboard will open in your default web browser")
    print("⏹️  Press Ctrl+C to stop the dashboard")
    print("-" * 60)
    
    try:
        # Launch Streamlit dashboard
        cmd = [
            sys.executable, "-m", "streamlit", "run", 
            str(dashboard_path),
            "--server.port", "8503",
            "--server.address", "localhost",
            "--browser.gatherUsageStats", "false"
        ]
        
        subprocess.run(cmd, cwd=str(script_dir))
        
    except KeyboardInterrupt:
        print("\n⏹️  Dashboard stopped by user")
        return 0
    except Exception as e:
        print(f"❌ Error launching dashboard: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
