#!/usr/bin/env python3
"""
Test script for email notification system
"""

import sys
import os
from pathlib import Path

# Add current directory to path
sys.path.append(str(Path(__file__).parent))

def test_email_system():
    """Test the email notification system"""
    print("📧 Testing Email Notification System")
    print("=" * 50)
    
    try:
        from security.email_notifications import get_email_service, send_access_request_email
        
        email_service = get_email_service()
        
        print(f"📋 Email Configuration:")
        print(f"   SMTP Host: {email_service.smtp_host}")
        print(f"   SMTP Port: {email_service.smtp_port}")
        print(f"   Username: {email_service.username}")
        print(f"   From Address: {email_service.from_address}")
        print(f"   Admin Address: {email_service.admin_address}")
        print(f"   Enabled: {email_service.enabled}")
        print()
        
        if not email_service.enabled:
            print("⚠️  Email system is disabled in configuration")
            print("   To enable: Set EMAIL_ENABLED=true in .env file")
            print("   Configure EMAIL_PASSWORD with Gmail app password")
            return
        
        if not email_service.password:
            print("⚠️  Email password not configured")
            print("   To configure:")
            print("   1. Go to Google Account settings")
            print("   2. Enable 2-factor authentication")
            print("   3. Generate an app password")
            print("   4. Set EMAIL_PASSWORD in .env file")
            return
        
        # Test access request email
        print("🧪 Testing access request email...")
        
        test_request = {
            'full_name': 'Test User',
            'email': 'test@example.com',
            'organization': 'Test Organization',
            'role_requested': 'Viewer',
            'counties': ['Kisumu'],
            'justification': 'Testing the email notification system'
        }
        
        success = send_access_request_email(test_request)
        
        if success:
            print("✅ Access request email test successful!")
            print(f"   Email sent to: {email_service.admin_address}")
        else:
            print("❌ Access request email test failed")
        
        print()
        print("📧 Email System Test Summary:")
        print(f"   Configuration: {'✅ Valid' if email_service.enabled else '❌ Disabled'}")
        print(f"   Credentials: {'✅ Configured' if email_service.password else '❌ Missing'}")
        print(f"   Test Email: {'✅ Sent' if success else '❌ Failed'}")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
    except Exception as e:
        print(f"❌ Error testing email system: {e}")

def show_email_setup_guide():
    """Show email setup guide"""
    print("\n📧 Email Setup Guide")
    print("=" * 30)
    
    print("""
To set up email notifications for access requests:

1. **Gmail App Password Setup:**
   - Go to Google Account settings (myaccount.google.com)
   - Security → 2-Step Verification (enable if not already)
   - Security → App passwords
   - Generate a new app password for "Ushauri AI"
   - Copy the 16-character password

2. **Update .env file:**
   ```
   EMAIL_ENABLED=true
   EMAIL_USERNAME=keyegon@gmail.com
   EMAIL_PASSWORD=your_16_character_app_password
   EMAIL_FROM_ADDRESS=keyegon@gmail.com
   EMAIL_ADMIN_ADDRESS=keyegon@gmail.com
   ```

3. **Test the system:**
   ```bash
   python test_email_system.py
   ```

4. **How it works:**
   - Users request access via the login page
   - Email notification sent to keyegon@gmail.com
   - Admin creates user account
   - Welcome email sent to new user with credentials

5. **Security Notes:**
   - Never share the app password
   - App password is different from your Gmail password
   - App password only works with 2FA enabled
   - Revoke app password if compromised
    """)

if __name__ == "__main__":
    test_email_system()
    show_email_setup_guide()
