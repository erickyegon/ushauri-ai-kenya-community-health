"""
User Management Interface for Kenya Health AI RBAC System
Provides Streamlit interface for managing users, roles, and permissions
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from typing import List, Optional

from .rbac import get_rbac_manager, UserRole, Permission, User
from .auth_decorators import protected_page, require_permission, get_current_user

@protected_page(
    title="👥 User Management",
    required_permissions=[Permission.MANAGE_USERS]
)
def show_user_management():
    """Main user management interface"""
    
    st.markdown("Manage system users, roles, and permissions")
    
    # Tabs for different management functions
    tab1, tab2, tab3, tab4 = st.tabs(["👤 Users", "🔑 Create User", "📊 Audit Log", "⚙️ Settings"])
    
    with tab1:
        show_users_list()
    
    with tab2:
        show_create_user_form()
    
    with tab3:
        show_audit_log()
    
    with tab4:
        show_rbac_settings()

def show_users_list():
    """Display list of all users"""
    st.subheader("📋 System Users")
    
    rbac = get_rbac_manager()
    
    try:
        # Get all users from database
        import sqlite3
        with sqlite3.connect(rbac.db_path) as conn:
            cursor = conn.execute('''
                SELECT user_id, username, email, full_name, role, counties, 
                       is_active, created_at, last_login, failed_login_attempts
                FROM users
                ORDER BY created_at DESC
            ''')
            
            users_data = []
            for row in cursor.fetchall():
                user_id, username, email, full_name, role, counties_json, is_active, created_at, last_login, failed_attempts = row
                
                import json
                counties = json.loads(counties_json) if counties_json else []
                
                users_data.append({
                    'User ID': user_id,
                    'Username': username,
                    'Full Name': full_name,
                    'Email': email,
                    'Role': role.replace('_', ' ').title(),
                    'Counties': ', '.join(counties) if counties else 'None',
                    'Status': '✅ Active' if is_active else '❌ Inactive',
                    'Created': datetime.fromisoformat(created_at).strftime('%Y-%m-%d'),
                    'Last Login': datetime.fromisoformat(last_login).strftime('%Y-%m-%d %H:%M') if last_login else 'Never',
                    'Failed Attempts': failed_attempts
                })
        
        if users_data:
            df = pd.DataFrame(users_data)
            
            # Display users table
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    'User ID': st.column_config.TextColumn('User ID', width='small'),
                    'Status': st.column_config.TextColumn('Status', width='small'),
                    'Failed Attempts': st.column_config.NumberColumn('Failed Attempts', width='small')
                }
            )
            
            # User actions
            st.subheader("🔧 User Actions")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                selected_username = st.selectbox(
                    "Select User",
                    options=[user['Username'] for user in users_data],
                    key="user_action_select"
                )
            
            with col2:
                action = st.selectbox(
                    "Action",
                    options=["Activate", "Deactivate", "Reset Password", "Delete"],
                    key="user_action_type"
                )
            
            with col3:
                if st.button("Execute Action", type="primary"):
                    execute_user_action(selected_username, action)
        
        else:
            st.info("No users found in the system")
    
    except Exception as e:
        st.error(f"Error loading users: {e}")

def show_create_user_form():
    """Display form to create new user"""
    st.subheader("➕ Create New User")
    
    with st.form("create_user_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            username = st.text_input("Username", placeholder="Enter username")
            email = st.text_input("Email", placeholder="user@example.com")
            full_name = st.text_input("Full Name", placeholder="Enter full name")
        
        with col2:
            role = st.selectbox("Role", options=[
                UserRole.ME_OFFICER.value,
                UserRole.HEALTH_SUPERVISOR.value,
                UserRole.COUNTY_MANAGER.value,
                UserRole.DATA_ANALYST.value,
                UserRole.VIEWER.value,
                UserRole.SYSTEM_ADMIN.value
            ])
            
            counties = st.multiselect(
                "Assigned Counties",
                options=["Kisumu", "Busia", "Vihiga"],
                help="Select counties this user can access"
            )
            
            password = st.text_input("Password", type="password", placeholder="Enter password")
            confirm_password = st.text_input("Confirm Password", type="password", placeholder="Confirm password")
        
        if st.form_submit_button("👤 Create User", type="primary"):
            if not all([username, email, full_name, password, confirm_password]):
                st.error("❌ Please fill in all required fields")
            elif password != confirm_password:
                st.error("❌ Passwords do not match")
            elif len(password) < 8:
                st.error("❌ Password must be at least 8 characters long")
            else:
                rbac = get_rbac_manager()
                
                if rbac.user_exists(username):
                    st.error(f"❌ Username '{username}' already exists")
                else:
                    try:
                        success = rbac.create_user(
                            username=username,
                            email=email,
                            password=password,
                            full_name=full_name,
                            role=UserRole(role),
                            counties=counties
                        )
                        
                        if success:
                            st.success(f"✅ User '{username}' created successfully!")

                            # Send welcome email with credentials
                            try:
                                from .email_notifications import send_access_approved_email
                                import secrets

                                # Generate temporary password
                                temp_password = secrets.token_urlsafe(12)

                                # Update user with temporary password
                                password_hash, salt = rbac._hash_password(temp_password)

                                import sqlite3
                                with sqlite3.connect(rbac.db_path) as conn:
                                    conn.execute('''
                                        UPDATE users SET password_hash = ?, salt = ?
                                        WHERE username = ?
                                    ''', (password_hash, salt, username))
                                    conn.commit()

                                # Send email
                                user_data = {
                                    'username': username,
                                    'email': email,
                                    'full_name': full_name,
                                    'role': role.replace('_', ' ').title(),
                                    'counties': counties
                                }

                                email_sent = send_access_approved_email(user_data, temp_password)

                                if email_sent:
                                    st.info(f"📧 Welcome email sent to {email} with login credentials")
                                else:
                                    st.warning(f"⚠️ User created but email notification failed")
                                    st.info(f"🔑 Temporary password: `{temp_password}`")

                            except Exception as e:
                                st.warning(f"⚠️ User created but email notification failed: {e}")

                            st.balloons()
                        else:
                            st.error("❌ Failed to create user")
                    
                    except Exception as e:
                        st.error(f"❌ Error creating user: {e}")

def show_audit_log():
    """Display audit log"""
    st.subheader("📊 Security Audit Log")
    
    rbac = get_rbac_manager()
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        action_filter = st.selectbox(
            "Filter by Action",
            options=["All", "LOGIN_SUCCESS", "LOGIN_FAILED", "USER_CREATED", "LOGOUT"],
            key="audit_action_filter"
        )
    
    with col2:
        days_back = st.number_input("Days Back", min_value=1, max_value=90, value=7)
    
    with col3:
        if st.button("🔄 Refresh Log"):
            st.rerun()
    
    try:
        import sqlite3
        with sqlite3.connect(rbac.db_path) as conn:
            # Build query based on filters
            query = '''
                SELECT timestamp, user_id, action, resource, details, ip_address, success
                FROM audit_log
                WHERE timestamp >= datetime('now', '-{} days')
            '''.format(days_back)
            
            params = []
            if action_filter != "All":
                query += " AND action = ?"
                params.append(action_filter)
            
            query += " ORDER BY timestamp DESC LIMIT 1000"
            
            cursor = conn.execute(query, params)
            
            audit_data = []
            for row in cursor.fetchall():
                timestamp, user_id, action, resource, details, ip_address, success = row
                
                audit_data.append({
                    'Timestamp': datetime.fromisoformat(timestamp).strftime('%Y-%m-%d %H:%M:%S'),
                    'User ID': user_id or 'System',
                    'Action': action,
                    'Resource': resource or '',
                    'Details': details or '',
                    'IP Address': ip_address or 'Unknown',
                    'Success': '✅' if success else '❌'
                })
        
        if audit_data:
            df = pd.DataFrame(audit_data)
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    'Success': st.column_config.TextColumn('Success', width='small'),
                    'User ID': st.column_config.TextColumn('User ID', width='medium')
                }
            )
            
            # Export option
            if st.button("📥 Export Audit Log"):
                csv = df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name=f"audit_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
        else:
            st.info("No audit log entries found for the selected criteria")
    
    except Exception as e:
        st.error(f"Error loading audit log: {e}")

def show_rbac_settings():
    """Display RBAC system settings"""
    st.subheader("⚙️ RBAC System Settings")
    
    # Role permissions matrix
    st.subheader("🔐 Role Permissions Matrix")
    
    # Create permissions matrix
    roles = list(UserRole)
    permissions = list(Permission)
    
    rbac = get_rbac_manager()
    
    # Build matrix data
    matrix_data = []
    for permission in permissions:
        row = {'Permission': permission.value.replace('_', ' ').title()}
        for role in roles:
            # Check if role has permission
            try:
                import sqlite3
                with sqlite3.connect(rbac.db_path) as conn:
                    cursor = conn.execute('''
                        SELECT 1 FROM role_permissions 
                        WHERE role = ? AND permission = ?
                    ''', (role.value, permission.value))
                    
                    has_permission = cursor.fetchone() is not None
                    row[role.value.replace('_', ' ').title()] = '✅' if has_permission else '❌'
            except:
                row[role.value.replace('_', ' ').title()] = '❓'
        
        matrix_data.append(row)
    
    if matrix_data:
        df = pd.DataFrame(matrix_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    
    # System statistics
    st.subheader("📈 System Statistics")
    
    try:
        import sqlite3
        with sqlite3.connect(rbac.db_path) as conn:
            # Total users
            cursor = conn.execute('SELECT COUNT(*) FROM users')
            total_users = cursor.fetchone()[0]
            
            # Active users
            cursor = conn.execute('SELECT COUNT(*) FROM users WHERE is_active = 1')
            active_users = cursor.fetchone()[0]
            
            # Active sessions
            cursor = conn.execute('SELECT COUNT(*) FROM sessions WHERE expires_at > ?', 
                                (datetime.now().isoformat(),))
            active_sessions = cursor.fetchone()[0]
            
            # Recent logins (last 24 hours)
            cursor = conn.execute('''
                SELECT COUNT(*) FROM audit_log 
                WHERE action = 'LOGIN_SUCCESS' AND timestamp >= datetime('now', '-1 day')
            ''')
            recent_logins = cursor.fetchone()[0]
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Users", total_users)
        
        with col2:
            st.metric("Active Users", active_users)
        
        with col3:
            st.metric("Active Sessions", active_sessions)
        
        with col4:
            st.metric("Logins (24h)", recent_logins)
    
    except Exception as e:
        st.error(f"Error loading statistics: {e}")
    
    # System maintenance
    st.subheader("🔧 System Maintenance")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🧹 Clean Expired Sessions"):
            rbac = get_rbac_manager()
            cleaned = rbac.cleanup_expired_sessions()
            st.success(f"Cleaned {cleaned} expired sessions")
    
    with col2:
        if st.button("🔄 Reset Failed Login Attempts"):
            try:
                import sqlite3
                with sqlite3.connect(rbac.db_path) as conn:
                    cursor = conn.execute('UPDATE users SET failed_login_attempts = 0, locked_until = NULL')
                    affected = cursor.rowcount
                    conn.commit()
                    st.success(f"Reset failed login attempts for {affected} users")
            except Exception as e:
                st.error(f"Error resetting login attempts: {e}")

def execute_user_action(username: str, action: str):
    """Execute user management action"""
    rbac = get_rbac_manager()
    
    try:
        import sqlite3
        with sqlite3.connect(rbac.db_path) as conn:
            if action == "Activate":
                conn.execute('UPDATE users SET is_active = 1 WHERE username = ?', (username,))
                conn.commit()
                st.success(f"✅ User '{username}' activated")
            
            elif action == "Deactivate":
                conn.execute('UPDATE users SET is_active = 0 WHERE username = ?', (username,))
                conn.commit()
                st.success(f"✅ User '{username}' deactivated")
            
            elif action == "Reset Password":
                # Generate temporary password
                import secrets
                temp_password = secrets.token_urlsafe(12)
                password_hash, salt = rbac._hash_password(temp_password)
                
                conn.execute('''
                    UPDATE users SET password_hash = ?, salt = ?, failed_login_attempts = 0, locked_until = NULL
                    WHERE username = ?
                ''', (password_hash, salt, username))
                conn.commit()
                
                st.success(f"✅ Password reset for '{username}'")
                st.info(f"🔑 Temporary password: `{temp_password}`")
                st.warning("⚠️ User should change this password on next login")
            
            elif action == "Delete":
                # Confirm deletion
                if st.button(f"⚠️ Confirm Delete '{username}'", type="secondary", key=f"confirm_delete_{username}"):
                    conn.execute('DELETE FROM users WHERE username = ?', (username,))
                    conn.commit()
                    st.success(f"✅ User '{username}' deleted")
                    st.rerun()
    
    except Exception as e:
        st.error(f"❌ Error executing action: {e}")

if __name__ == "__main__":
    show_user_management()
