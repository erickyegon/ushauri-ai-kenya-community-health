"""
Role-Based Access Control (RBAC) System for Kenya Health AI
Implements comprehensive user authentication, authorization, and role management
"""

import os
import sqlite3
import hashlib
import secrets
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import streamlit as st
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class UserRole(Enum):
    """User roles in the Kenya Health AI system"""
    SUPER_ADMIN = "super_admin"
    SYSTEM_ADMIN = "system_admin"
    ME_OFFICER = "me_officer"  # M&E Officer
    HEALTH_SUPERVISOR = "health_supervisor"
    COUNTY_MANAGER = "county_manager"  # County Health Management Team
    DATA_ANALYST = "data_analyst"
    VIEWER = "viewer"
    GUEST = "guest"

class Permission(Enum):
    """System permissions"""
    # System Administration
    MANAGE_USERS = "manage_users"
    MANAGE_ROLES = "manage_roles"
    SYSTEM_CONFIG = "system_config"
    VIEW_AUDIT_LOGS = "view_audit_logs"
    
    # Data Access
    VIEW_ALL_COUNTIES = "view_all_counties"
    VIEW_ASSIGNED_COUNTIES = "view_assigned_counties"
    VIEW_SENSITIVE_DATA = "view_sensitive_data"
    EXPORT_DATA = "export_data"
    
    # Analysis and Reporting
    RUN_ANALYSIS = "run_analysis"
    CREATE_REPORTS = "create_reports"
    SCHEDULE_REPORTS = "schedule_reports"
    VIEW_PERFORMANCE_METRICS = "view_performance_metrics"
    
    # CHW Management
    MANAGE_CHW_DATA = "manage_chw_data"
    VIEW_CHW_PERFORMANCE = "view_chw_performance"
    ASSIGN_CHW_SUPERVISORS = "assign_chw_supervisors"
    
    # System Operations
    CACHE_MANAGEMENT = "cache_management"
    PERFORMANCE_MONITORING = "performance_monitoring"
    DATABASE_ACCESS = "database_access"

@dataclass
class User:
    """User data model"""
    user_id: str
    username: str
    email: str
    full_name: str
    role: UserRole
    counties: List[str]  # Assigned counties
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None

@dataclass
class Session:
    """User session data model"""
    session_id: str
    user_id: str
    created_at: datetime
    expires_at: datetime
    ip_address: str
    user_agent: str

class RBACManager:
    """Role-Based Access Control Manager"""
    
    def __init__(self, db_path: str = "security/rbac.db"):
        self.db_path = db_path
        self.audit_log_path = "security/rbac_audit.log"
        
        # Ensure security directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Initialize database
        self._init_database()
        
        # Define role permissions
        self._init_role_permissions()
        
        # Create default admin user if none exists
        self._create_default_admin()
    
    def _init_database(self):
        """Initialize RBAC database"""
        with sqlite3.connect(self.db_path) as conn:
            # Users table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    full_name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    counties TEXT,  -- JSON array of assigned counties
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    failed_login_attempts INTEGER DEFAULT 0,
                    locked_until TIMESTAMP
                )
            ''')
            
            # Sessions table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    ip_address TEXT,
                    user_agent TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Audit log table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    user_id TEXT,
                    action TEXT NOT NULL,
                    resource TEXT,
                    details TEXT,
                    ip_address TEXT,
                    success BOOLEAN
                )
            ''')
            
            # Role permissions table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS role_permissions (
                    role TEXT NOT NULL,
                    permission TEXT NOT NULL,
                    PRIMARY KEY (role, permission)
                )
            ''')
            
            conn.commit()
    
    def _init_role_permissions(self):
        """Initialize role-permission mappings"""
        role_permissions = {
            UserRole.SUPER_ADMIN: [p for p in Permission],  # All permissions
            
            UserRole.SYSTEM_ADMIN: [
                Permission.MANAGE_USERS, Permission.MANAGE_ROLES, Permission.SYSTEM_CONFIG,
                Permission.VIEW_AUDIT_LOGS, Permission.VIEW_ALL_COUNTIES, Permission.VIEW_SENSITIVE_DATA,
                Permission.EXPORT_DATA, Permission.RUN_ANALYSIS, Permission.CREATE_REPORTS,
                Permission.SCHEDULE_REPORTS, Permission.VIEW_PERFORMANCE_METRICS,
                Permission.CACHE_MANAGEMENT, Permission.PERFORMANCE_MONITORING, Permission.DATABASE_ACCESS
            ],
            
            UserRole.ME_OFFICER: [
                Permission.VIEW_ALL_COUNTIES, Permission.VIEW_SENSITIVE_DATA, Permission.EXPORT_DATA,
                Permission.RUN_ANALYSIS, Permission.CREATE_REPORTS, Permission.SCHEDULE_REPORTS,
                Permission.VIEW_PERFORMANCE_METRICS, Permission.VIEW_CHW_PERFORMANCE
            ],
            
            UserRole.HEALTH_SUPERVISOR: [
                Permission.VIEW_ASSIGNED_COUNTIES, Permission.RUN_ANALYSIS, Permission.CREATE_REPORTS,
                Permission.VIEW_PERFORMANCE_METRICS, Permission.VIEW_CHW_PERFORMANCE,
                Permission.MANAGE_CHW_DATA, Permission.ASSIGN_CHW_SUPERVISORS
            ],
            
            UserRole.COUNTY_MANAGER: [
                Permission.VIEW_ASSIGNED_COUNTIES, Permission.VIEW_SENSITIVE_DATA, Permission.EXPORT_DATA,
                Permission.RUN_ANALYSIS, Permission.CREATE_REPORTS, Permission.VIEW_PERFORMANCE_METRICS,
                Permission.VIEW_CHW_PERFORMANCE, Permission.MANAGE_CHW_DATA
            ],
            
            UserRole.DATA_ANALYST: [
                Permission.VIEW_ALL_COUNTIES, Permission.RUN_ANALYSIS, Permission.CREATE_REPORTS,
                Permission.VIEW_PERFORMANCE_METRICS, Permission.EXPORT_DATA
            ],
            
            UserRole.VIEWER: [
                Permission.VIEW_ASSIGNED_COUNTIES, Permission.RUN_ANALYSIS, Permission.VIEW_PERFORMANCE_METRICS
            ],
            
            UserRole.GUEST: [
                Permission.VIEW_ASSIGNED_COUNTIES
            ]
        }
        
        with sqlite3.connect(self.db_path) as conn:
            # Clear existing permissions
            conn.execute('DELETE FROM role_permissions')
            
            # Insert role permissions
            for role, permissions in role_permissions.items():
                for permission in permissions:
                    conn.execute(
                        'INSERT INTO role_permissions (role, permission) VALUES (?, ?)',
                        (role.value, permission.value)
                    )
            
            conn.commit()
    
    def _create_default_admin(self):
        """Create default admin user if none exists"""
        if not self.user_exists("admin"):
            admin_password = os.getenv("DEFAULT_ADMIN_PASSWORD", "KenyaHealth2025!")
            admin_email = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@kenya-health-ai.com")
            
            self.create_user(
                username="admin",
                email=admin_email,
                password=admin_password,
                full_name="System Administrator",
                role=UserRole.SUPER_ADMIN,
                counties=["Kisumu", "Busia", "Vihiga"]
            )
            
            logger.info("Default admin user created")
    
    def _hash_password(self, password: str, salt: str = None) -> Tuple[str, str]:
        """Hash password with salt"""
        if salt is None:
            salt = secrets.token_hex(32)
        
        password_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000  # iterations
        )
        
        return password_hash.hex(), salt
    
    def _verify_password(self, password: str, password_hash: str, salt: str) -> bool:
        """Verify password against hash"""
        computed_hash, _ = self._hash_password(password, salt)
        return secrets.compare_digest(computed_hash, password_hash)
    
    def _log_audit(self, user_id: str, action: str, resource: str = None, 
                   details: str = None, ip_address: str = None, success: bool = True):
        """Log audit event"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT INTO audit_log (user_id, action, resource, details, ip_address, success)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, action, resource, details, ip_address, success))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")
    
    def create_user(self, username: str, email: str, password: str, full_name: str,
                   role: UserRole, counties: List[str] = None) -> bool:
        """Create a new user"""
        try:
            user_id = secrets.token_urlsafe(16)
            password_hash, salt = self._hash_password(password)
            counties_json = json.dumps(counties or [])
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT INTO users (user_id, username, email, password_hash, salt, 
                                     full_name, role, counties, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                ''', (user_id, username, email, password_hash, salt, full_name, 
                      role.value, counties_json))
                conn.commit()
            
            self._log_audit(user_id, "USER_CREATED", f"user:{username}")
            logger.info(f"User created: {username}")
            return True
            
        except sqlite3.IntegrityError as e:
            logger.error(f"Failed to create user {username}: {e}")
            return False
    
    def authenticate(self, username: str, password: str, ip_address: str = None) -> Optional[str]:
        """Authenticate user and return session ID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT user_id, password_hash, salt, is_active, failed_login_attempts, locked_until
                    FROM users WHERE username = ?
                ''', (username,))
                
                row = cursor.fetchone()
                if not row:
                    self._log_audit(None, "LOGIN_FAILED", f"user:{username}", "User not found", ip_address, False)
                    return None
                
                user_id, password_hash, salt, is_active, failed_attempts, locked_until = row
                
                # Check if account is locked
                if locked_until:
                    locked_until_dt = datetime.fromisoformat(locked_until)
                    if datetime.now() < locked_until_dt:
                        self._log_audit(user_id, "LOGIN_FAILED", f"user:{username}", "Account locked", ip_address, False)
                        return None
                
                # Check if account is active
                if not is_active:
                    self._log_audit(user_id, "LOGIN_FAILED", f"user:{username}", "Account inactive", ip_address, False)
                    return None
                
                # Verify password
                if not self._verify_password(password, password_hash, salt):
                    # Increment failed attempts
                    failed_attempts += 1
                    max_attempts = int(os.getenv("RBAC_MAX_LOGIN_ATTEMPTS", 3))
                    
                    if failed_attempts >= max_attempts:
                        # Lock account
                        lockout_duration = int(os.getenv("RBAC_LOCKOUT_DURATION", 900))  # 15 minutes
                        locked_until = datetime.now() + timedelta(seconds=lockout_duration)
                        
                        conn.execute('''
                            UPDATE users SET failed_login_attempts = ?, locked_until = ?
                            WHERE user_id = ?
                        ''', (failed_attempts, locked_until.isoformat(), user_id))
                    else:
                        conn.execute('''
                            UPDATE users SET failed_login_attempts = ?
                            WHERE user_id = ?
                        ''', (failed_attempts, user_id))
                    
                    conn.commit()
                    self._log_audit(user_id, "LOGIN_FAILED", f"user:{username}", "Invalid password", ip_address, False)
                    return None
                
                # Reset failed attempts on successful login
                conn.execute('''
                    UPDATE users SET failed_login_attempts = 0, locked_until = NULL, last_login = ?
                    WHERE user_id = ?
                ''', (datetime.now().isoformat(), user_id))
                
                # Create session
                session_id = secrets.token_urlsafe(32)
                session_timeout = int(os.getenv("RBAC_SESSION_TIMEOUT", 3600))
                expires_at = datetime.now() + timedelta(seconds=session_timeout)
                
                conn.execute('''
                    INSERT INTO sessions (session_id, user_id, expires_at, ip_address)
                    VALUES (?, ?, ?, ?)
                ''', (session_id, user_id, expires_at.isoformat(), ip_address))
                
                conn.commit()
                
                self._log_audit(user_id, "LOGIN_SUCCESS", f"user:{username}", None, ip_address, True)
                logger.info(f"User authenticated: {username}")
                return session_id
                
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return None
    
    def get_user_by_session(self, session_id: str) -> Optional[User]:
        """Get user by session ID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT u.user_id, u.username, u.email, u.full_name, u.role, 
                           u.counties, u.is_active, u.created_at, u.last_login,
                           u.failed_login_attempts, u.locked_until
                    FROM users u
                    JOIN sessions s ON u.user_id = s.user_id
                    WHERE s.session_id = ? AND s.expires_at > ?
                ''', (session_id, datetime.now().isoformat()))
                
                row = cursor.fetchone()
                if not row:
                    return None
                
                user_id, username, email, full_name, role, counties_json, is_active, created_at, last_login, failed_attempts, locked_until = row
                
                counties = json.loads(counties_json) if counties_json else []
                
                return User(
                    user_id=user_id,
                    username=username,
                    email=email,
                    full_name=full_name,
                    role=UserRole(role),
                    counties=counties,
                    is_active=bool(is_active),
                    created_at=datetime.fromisoformat(created_at),
                    last_login=datetime.fromisoformat(last_login) if last_login else None,
                    failed_login_attempts=failed_attempts,
                    locked_until=datetime.fromisoformat(locked_until) if locked_until else None
                )
                
        except Exception as e:
            logger.error(f"Error getting user by session: {e}")
            return None
    
    def has_permission(self, user: User, permission: Permission) -> bool:
        """Check if user has specific permission"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT 1 FROM role_permissions 
                    WHERE role = ? AND permission = ?
                ''', (user.role.value, permission.value))
                
                return cursor.fetchone() is not None
                
        except Exception as e:
            logger.error(f"Error checking permission: {e}")
            return False
    
    def can_access_county(self, user: User, county: str) -> bool:
        """Check if user can access specific county data"""
        # Super admin and system admin can access all counties
        if user.role in [UserRole.SUPER_ADMIN, UserRole.SYSTEM_ADMIN]:
            return True
        
        # M&E Officers and Data Analysts can access all counties
        if user.role in [UserRole.ME_OFFICER, UserRole.DATA_ANALYST]:
            return self.has_permission(user, Permission.VIEW_ALL_COUNTIES)
        
        # Other roles can only access assigned counties
        return county in user.counties
    
    def logout(self, session_id: str) -> bool:
        """Logout user by invalidating session"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Get user info for audit log
                cursor = conn.execute('''
                    SELECT u.user_id, u.username FROM users u
                    JOIN sessions s ON u.user_id = s.user_id
                    WHERE s.session_id = ?
                ''', (session_id,))
                
                row = cursor.fetchone()
                if row:
                    user_id, username = row
                    self._log_audit(user_id, "LOGOUT", f"user:{username}")
                
                # Delete session
                conn.execute('DELETE FROM sessions WHERE session_id = ?', (session_id,))
                conn.commit()
                
                return True
                
        except Exception as e:
            logger.error(f"Error during logout: {e}")
            return False
    
    def user_exists(self, username: str) -> bool:
        """Check if user exists"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('SELECT 1 FROM users WHERE username = ?', (username,))
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Error checking user existence: {e}")
            return False
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    DELETE FROM sessions WHERE expires_at < ?
                ''', (datetime.now().isoformat(),))
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                if deleted_count > 0:
                    logger.info(f"Cleaned up {deleted_count} expired sessions")
                
                return deleted_count
                
        except Exception as e:
            logger.error(f"Error cleaning up sessions: {e}")
            return 0

# Global RBAC manager instance
_rbac_manager = None

def get_rbac_manager() -> RBACManager:
    """Get global RBAC manager instance"""
    global _rbac_manager
    if _rbac_manager is None:
        _rbac_manager = RBACManager()
    return _rbac_manager
