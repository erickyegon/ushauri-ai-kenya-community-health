"""
Authentication Decorators and Middleware for Kenya Health AI
Provides decorators for protecting functions and Streamlit pages with RBAC
"""

import functools
import streamlit as st
from typing import List, Optional, Callable, Any
import logging

from .rbac import get_rbac_manager, UserRole, Permission, User

logger = logging.getLogger(__name__)

def require_auth(redirect_to_login: bool = True):
    """
    Decorator to require authentication for a function
    
    Args:
        redirect_to_login: Whether to redirect to login page if not authenticated
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not is_authenticated():
                if redirect_to_login:
                    show_login_page()
                    return None
                else:
                    st.error("🔒 Authentication required")
                    st.stop()
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

def require_permission(permission: Permission, show_error: bool = True):
    """
    Decorator to require specific permission for a function
    
    Args:
        permission: Required permission
        show_error: Whether to show error message if permission denied
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if not user:
                if show_error:
                    st.error("🔒 Authentication required")
                st.stop()
            
            rbac = get_rbac_manager()
            if not rbac.has_permission(user, permission):
                if show_error:
                    st.error(f"🚫 Access denied. Required permission: {permission.value}")
                st.stop()
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

def require_role(roles: List[UserRole], show_error: bool = True):
    """
    Decorator to require specific role(s) for a function
    
    Args:
        roles: List of allowed roles
        show_error: Whether to show error message if role not allowed
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if not user:
                if show_error:
                    st.error("🔒 Authentication required")
                st.stop()
            
            if user.role not in roles:
                if show_error:
                    allowed_roles = ", ".join([role.value for role in roles])
                    st.error(f"🚫 Access denied. Required role(s): {allowed_roles}")
                st.stop()
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

def require_county_access(county: str, show_error: bool = True):
    """
    Decorator to require access to specific county
    
    Args:
        county: County name to check access for
        show_error: Whether to show error message if access denied
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if not user:
                if show_error:
                    st.error("🔒 Authentication required")
                st.stop()
            
            rbac = get_rbac_manager()
            if not rbac.can_access_county(user, county):
                if show_error:
                    st.error(f"🚫 Access denied to {county} county data")
                st.stop()
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

def is_authenticated() -> bool:
    """Check if current user is authenticated"""
    return get_current_user() is not None

def get_current_user() -> Optional[User]:
    """Get current authenticated user"""
    if 'session_id' not in st.session_state:
        return None
    
    rbac = get_rbac_manager()
    user = rbac.get_user_by_session(st.session_state.session_id)
    
    if user is None:
        # Clear invalid session
        if 'session_id' in st.session_state:
            del st.session_state.session_id
    
    return user

def login(username: str, password: str) -> bool:
    """
    Login user and create session
    
    Args:
        username: Username
        password: Password
    
    Returns:
        True if login successful, False otherwise
    """
    rbac = get_rbac_manager()
    
    # Get client IP (best effort)
    ip_address = st.context.headers.get('x-forwarded-for', 'unknown')
    
    session_id = rbac.authenticate(username, password, ip_address)
    
    if session_id:
        st.session_state.session_id = session_id
        st.session_state.user = rbac.get_user_by_session(session_id)
        return True
    
    return False

def logout():
    """Logout current user"""
    if 'session_id' in st.session_state:
        rbac = get_rbac_manager()
        rbac.logout(st.session_state.session_id)
        
        # Clear session state
        del st.session_state.session_id
        if 'user' in st.session_state:
            del st.session_state.user

def show_login_page():
    """Display login page"""
    st.title("🏥 Ushauri AI - Login")
    
    # Check if already authenticated
    if is_authenticated():
        st.success("✅ Already logged in")
        if st.button("Continue to Dashboard", key="continue_to_dashboard"):
            st.rerun()
        return
    
    with st.form("login_form"):
        st.subheader("🔐 User Authentication")
        
        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        
        col1, col2 = st.columns(2)
        
        with col1:
            login_button = st.form_submit_button("🔑 Login", use_container_width=True)
        
        with col2:
            if st.form_submit_button("👤 Request Access", use_container_width=True):
                show_access_request_form()
        
        if login_button:
            if not username or not password:
                st.error("❌ Please enter both username and password")
            else:
                with st.spinner("🔍 Authenticating..."):
                    if login(username, password):
                        st.success("✅ Login successful!")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error("❌ Invalid username or password")
    
    # Show system information
    with st.expander("ℹ️ System Information"):
        st.info("""
        **Ushauri AI - Kenya Community Health Systems**
        
        This system provides data analysis and reporting capabilities for Community Health Workers (CHWs) 
        in Kisumu, Busia, and Vihiga counties.
        
        **User Roles:**
        - **M&E Officers**: Full access to all counties and reporting
        - **Health Supervisors**: Access to assigned counties and CHW management
        - **County Managers**: County-level access and management
        - **Data Analysts**: Analysis and reporting capabilities
        - **Viewers**: Read-only access to assigned data
        
        **Default Admin Credentials** (Change in production):
        - Username: `admin`
        - Password: `KenyaHealth2025!`
        """)

def show_access_request_form():
    """Show access request form"""
    st.subheader("📝 Request System Access")
    
    with st.form("access_request_form"):
        full_name = st.text_input("Full Name", placeholder="Enter your full name")
        email = st.text_input("Email", placeholder="Enter your email address")
        organization = st.text_input("Organization", placeholder="Ministry of Health, County Government, etc.")
        role_requested = st.selectbox("Role Requested", [
            "M&E Officer",
            "Health Supervisor", 
            "County Manager",
            "Data Analyst",
            "Viewer"
        ])
        counties = st.multiselect("Counties", ["Kisumu", "Busia", "Vihiga"])
        justification = st.text_area("Justification", placeholder="Explain why you need access to this system")
        
        if st.form_submit_button("📤 Submit Request"):
            if all([full_name, email, organization, justification]):
                # Send email notification
                try:
                    from .email_notifications import send_access_request_email

                    request_data = {
                        'full_name': full_name,
                        'email': email,
                        'organization': organization,
                        'role_requested': role_requested,
                        'counties': counties,
                        'justification': justification
                    }

                    email_sent = send_access_request_email(request_data)

                    if email_sent:
                        st.success("""
                        ✅ **Access request submitted successfully!**

                        Your request has been forwarded to the system administrators at keyegon@gmail.com.
                        You will receive an email notification once your access has been reviewed and approved.

                        **Request Details:**
                        - Name: {full_name}
                        - Email: {email}
                        - Organization: {organization}
                        - Role: {role_requested}
                        - Counties: {counties}

                        **Next Steps:**
                        1. Admin will review your request
                        2. You'll receive login credentials via email
                        3. Log in and change your temporary password
                        """.format(
                            full_name=full_name,
                            email=email,
                            organization=organization,
                            role_requested=role_requested,
                            counties=", ".join(counties) if counties else "None specified"
                        ))
                    else:
                        st.warning("""
                        ⚠️ **Request submitted but email notification failed**

                        Your request has been logged but the email notification could not be sent.
                        Please contact the administrator directly at keyegon@gmail.com with your request details.
                        """)

                except ImportError:
                    st.info("""
                    ℹ️ **Request logged locally**

                    Email system not configured. Please contact the administrator at keyegon@gmail.com
                    with your request details.
                    """)
            else:
                st.error("❌ Please fill in all required fields")

def show_user_info():
    """Display current user information in sidebar"""
    user = get_current_user()
    if user:
        with st.sidebar:
            st.subheader("👤 User Information")
            st.write(f"**Name:** {user.full_name}")
            st.write(f"**Username:** {user.username}")
            st.write(f"**Role:** {user.role.value.replace('_', ' ').title()}")
            
            if user.counties:
                st.write(f"**Counties:** {', '.join(user.counties)}")
            
            if user.last_login:
                st.write(f"**Last Login:** {user.last_login.strftime('%Y-%m-%d %H:%M')}")
            
            # Use completely unique key based on user and timestamp
            import time
            import hashlib
            unique_key = f"logout_{user.user_id}_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}"

            if st.button("🚪 Logout", use_container_width=True, key=unique_key):
                logout()
                st.rerun()

def check_session_validity():
    """Check if current session is still valid"""
    if 'session_id' in st.session_state:
        user = get_current_user()
        if user is None:
            # Session expired or invalid
            st.warning("⚠️ Your session has expired. Please log in again.")
            logout()
            st.rerun()

def init_auth_system():
    """Initialize authentication system for Streamlit app"""
    # Clean up expired sessions periodically
    rbac = get_rbac_manager()
    rbac.cleanup_expired_sessions()
    
    # Check session validity
    check_session_validity()

# Streamlit page protection decorator
def protected_page(title: str = None, required_permissions: List[Permission] = None, 
                  required_roles: List[UserRole] = None, required_counties: List[str] = None):
    """
    Decorator for protecting entire Streamlit pages
    
    Args:
        title: Page title to display
        required_permissions: List of required permissions
        required_roles: List of required roles
        required_counties: List of counties user must have access to
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Initialize auth system
            init_auth_system()
            
            # Check authentication
            if not is_authenticated():
                show_login_page()
                return
            
            user = get_current_user()
            rbac = get_rbac_manager()
            
            # Check role requirements
            if required_roles and user.role not in required_roles:
                st.error(f"🚫 Access denied. Required role(s): {', '.join([r.value for r in required_roles])}")
                st.stop()
            
            # Check permission requirements
            if required_permissions:
                for permission in required_permissions:
                    if not rbac.has_permission(user, permission):
                        st.error(f"🚫 Access denied. Required permission: {permission.value}")
                        st.stop()
            
            # Check county access requirements
            if required_counties:
                for county in required_counties:
                    if not rbac.can_access_county(user, county):
                        st.error(f"🚫 Access denied to {county} county data")
                        st.stop()
            
            # Set page title
            if title:
                st.title(title)
            
            # Show user info in sidebar
            show_user_info()

            # Call the protected function
            return func(*args, **kwargs)
        
        return wrapper
    return decorator
