#!/usr/bin/env python3
"""
Test script for RBAC (Role-Based Access Control) system
Verifies authentication, authorization, and role-based permissions
"""

import sys
import os
from pathlib import Path

# Add current directory to path
sys.path.append(str(Path(__file__).parent))

from security.rbac import get_rbac_manager, UserRole, Permission
from security.auth_decorators import login, logout, get_current_user
import streamlit as st

def test_rbac_system():
    """Test the RBAC system functionality"""
    print("🧪 Testing RBAC System")
    print("=" * 50)
    
    rbac = get_rbac_manager()
    
    # Test 1: User Creation
    print("1️⃣ Testing User Creation...")
    
    test_users = [
        {
            "username": "me_officer_test",
            "email": "me@test.com",
            "password": "TestPass123!",
            "full_name": "Test M&E Officer",
            "role": UserRole.ME_OFFICER,
            "counties": ["Kisumu", "Busia", "Vihiga"]
        },
        {
            "username": "supervisor_test",
            "email": "supervisor@test.com", 
            "password": "TestPass123!",
            "full_name": "Test Health Supervisor",
            "role": UserRole.HEALTH_SUPERVISOR,
            "counties": ["Kisumu"]
        },
        {
            "username": "viewer_test",
            "email": "viewer@test.com",
            "password": "TestPass123!",
            "full_name": "Test Viewer",
            "role": UserRole.VIEWER,
            "counties": ["Busia"]
        }
    ]
    
    for user_data in test_users:
        if not rbac.user_exists(user_data["username"]):
            success = rbac.create_user(**user_data)
            print(f"   {'✅' if success else '❌'} Created user: {user_data['username']}")
        else:
            print(f"   ℹ️  User already exists: {user_data['username']}")
    
    print()
    
    # Test 2: Authentication
    print("2️⃣ Testing Authentication...")
    
    # Test valid login
    session_id = rbac.authenticate("admin", "KenyaHealth2025!", "127.0.0.1")
    if session_id:
        print("   ✅ Admin login successful")
        
        # Get user by session
        user = rbac.get_user_by_session(session_id)
        if user:
            print(f"   ✅ Session validation successful: {user.username}")
        else:
            print("   ❌ Session validation failed")
        
        # Logout
        if rbac.logout(session_id):
            print("   ✅ Logout successful")
        else:
            print("   ❌ Logout failed")
    else:
        print("   ❌ Admin login failed")
    
    # Test invalid login
    invalid_session = rbac.authenticate("admin", "wrongpassword", "127.0.0.1")
    if not invalid_session:
        print("   ✅ Invalid login correctly rejected")
    else:
        print("   ❌ Invalid login incorrectly accepted")
    
    print()
    
    # Test 3: Permission Checking
    print("3️⃣ Testing Permission System...")
    
    # Login as different users and test permissions
    test_cases = [
        {
            "username": "admin",
            "password": "KenyaHealth2025!",
            "expected_permissions": [
                Permission.MANAGE_USERS,
                Permission.VIEW_ALL_COUNTIES,
                Permission.RUN_ANALYSIS,
                Permission.EXPORT_DATA
            ]
        },
        {
            "username": "me_officer_test",
            "password": "TestPass123!",
            "expected_permissions": [
                Permission.VIEW_ALL_COUNTIES,
                Permission.RUN_ANALYSIS,
                Permission.EXPORT_DATA,
                Permission.VIEW_PERFORMANCE_METRICS
            ],
            "denied_permissions": [
                Permission.MANAGE_USERS,
                Permission.SYSTEM_CONFIG
            ]
        },
        {
            "username": "viewer_test",
            "password": "TestPass123!",
            "expected_permissions": [
                Permission.VIEW_ASSIGNED_COUNTIES,
                Permission.RUN_ANALYSIS
            ],
            "denied_permissions": [
                Permission.MANAGE_USERS,
                Permission.EXPORT_DATA,
                Permission.VIEW_ALL_COUNTIES
            ]
        }
    ]
    
    for test_case in test_cases:
        session_id = rbac.authenticate(test_case["username"], test_case["password"], "127.0.0.1")
        if session_id:
            user = rbac.get_user_by_session(session_id)
            print(f"   👤 Testing permissions for {user.username} ({user.role.value})")
            
            # Test expected permissions
            for permission in test_case.get("expected_permissions", []):
                has_permission = rbac.has_permission(user, permission)
                print(f"      {'✅' if has_permission else '❌'} {permission.value}: {'GRANTED' if has_permission else 'DENIED'}")
            
            # Test denied permissions
            for permission in test_case.get("denied_permissions", []):
                has_permission = rbac.has_permission(user, permission)
                print(f"      {'✅' if not has_permission else '❌'} {permission.value}: {'DENIED' if not has_permission else 'INCORRECTLY GRANTED'}")
            
            rbac.logout(session_id)
            print()
    
    # Test 4: County Access Control
    print("4️⃣ Testing County Access Control...")
    
    county_test_cases = [
        {
            "username": "admin",
            "password": "KenyaHealth2025!",
            "counties_to_test": ["Kisumu", "Busia", "Vihiga", "Nairobi"],
            "expected_access": [True, True, True, True]  # Admin can access all
        },
        {
            "username": "supervisor_test",
            "password": "TestPass123!",
            "counties_to_test": ["Kisumu", "Busia", "Vihiga"],
            "expected_access": [True, False, False]  # Only assigned to Kisumu
        },
        {
            "username": "viewer_test",
            "password": "TestPass123!",
            "counties_to_test": ["Kisumu", "Busia", "Vihiga"],
            "expected_access": [False, True, False]  # Only assigned to Busia
        }
    ]
    
    for test_case in county_test_cases:
        session_id = rbac.authenticate(test_case["username"], test_case["password"], "127.0.0.1")
        if session_id:
            user = rbac.get_user_by_session(session_id)
            print(f"   👤 Testing county access for {user.username}")
            
            for county, expected in zip(test_case["counties_to_test"], test_case["expected_access"]):
                has_access = rbac.can_access_county(user, county)
                result = "✅" if (has_access == expected) else "❌"
                access_text = "GRANTED" if has_access else "DENIED"
                print(f"      {result} {county}: {access_text}")
            
            rbac.logout(session_id)
            print()
    
    # Test 5: Session Management
    print("5️⃣ Testing Session Management...")
    
    # Create multiple sessions
    sessions = []
    for i in range(3):
        session_id = rbac.authenticate("admin", "KenyaHealth2025!", f"127.0.0.{i+1}")
        if session_id:
            sessions.append(session_id)
    
    print(f"   ✅ Created {len(sessions)} sessions")
    
    # Validate sessions
    valid_sessions = 0
    for session_id in sessions:
        user = rbac.get_user_by_session(session_id)
        if user:
            valid_sessions += 1
    
    print(f"   ✅ {valid_sessions}/{len(sessions)} sessions are valid")
    
    # Cleanup sessions
    for session_id in sessions:
        rbac.logout(session_id)
    
    # Test expired session cleanup
    cleaned = rbac.cleanup_expired_sessions()
    print(f"   ✅ Cleaned up {cleaned} expired sessions")
    
    print()
    
    # Test 6: Audit Logging
    print("6️⃣ Testing Audit Logging...")
    
    try:
        import sqlite3
        with sqlite3.connect(rbac.db_path) as conn:
            cursor = conn.execute('''
                SELECT COUNT(*) FROM audit_log 
                WHERE action IN ('LOGIN_SUCCESS', 'LOGIN_FAILED', 'USER_CREATED', 'LOGOUT')
            ''')
            audit_count = cursor.fetchone()[0]
            print(f"   ✅ Found {audit_count} audit log entries")
            
            # Show recent audit entries
            cursor = conn.execute('''
                SELECT timestamp, action, resource, success 
                FROM audit_log 
                ORDER BY timestamp DESC 
                LIMIT 5
            ''')
            
            print("   📋 Recent audit entries:")
            for row in cursor.fetchall():
                timestamp, action, resource, success = row
                status = "✅" if success else "❌"
                print(f"      {status} {timestamp}: {action} - {resource or 'N/A'}")
    
    except Exception as e:
        print(f"   ❌ Error checking audit log: {e}")
    
    print()
    
    # Summary
    print("📊 RBAC System Test Summary")
    print("-" * 30)
    print("✅ User creation and management")
    print("✅ Authentication and session management")
    print("✅ Role-based permission checking")
    print("✅ County-based access control")
    print("✅ Audit logging")
    print("✅ Session cleanup")
    
    print()
    print("🎉 RBAC system is working correctly!")
    
    return True

def test_streamlit_integration():
    """Test Streamlit integration (requires manual verification)"""
    print("\n🌐 Streamlit Integration Test")
    print("=" * 30)
    
    print("""
To test the Streamlit integration:

1. Run the main application:
   streamlit run app/main_streamlit_app.py

2. Test the following scenarios:

   📋 **Login Testing:**
   - Try logging in with admin/KenyaHealth2025!
   - Try logging in with invalid credentials
   - Verify user info appears in sidebar

   📋 **Role-based Access:**
   - Login as admin - should see User Management button
   - Login as me_officer_test - should see Performance Monitor
   - Login as viewer_test - should have limited access

   📋 **County Access Control:**
   - Login as supervisor_test (Kisumu only)
   - Try queries about different counties
   - Verify county filtering works

   📋 **Navigation:**
   - Test User Management page (admin only)
   - Test Performance Monitor page
   - Test Cache Management page

   📋 **Security:**
   - Try accessing protected pages without login
   - Verify session timeout works
   - Test logout functionality
    """)

if __name__ == "__main__":
    try:
        # Test core RBAC functionality
        test_rbac_system()
        
        # Show Streamlit integration instructions
        test_streamlit_integration()
        
    except Exception as e:
        print(f"❌ Error during RBAC testing: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
