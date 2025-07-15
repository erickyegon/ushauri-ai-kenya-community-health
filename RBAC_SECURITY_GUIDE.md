# Ushauri AI - RBAC Security Implementation Guide
## Kenya Community Health Systems

## 🔐 Overview

The Ushauri AI system now includes a comprehensive Role-Based Access Control (RBAC) system that provides secure authentication, authorization, and data access control based on user roles and county assignments.

## 🏗️ System Architecture

### Core Components

```
📁 security/
├── rbac.py                 # Core RBAC system
├── auth_decorators.py      # Authentication decorators
└── user_management.py      # User management interface
```

### Database Schema

- **Users Table**: User accounts, roles, and county assignments
- **Sessions Table**: Active user sessions with expiration
- **Audit Log Table**: Security events and access attempts
- **Role Permissions Table**: Role-permission mappings

## 👥 User Roles and Permissions

### Role Hierarchy

1. **🔴 Super Admin** - Full system access
2. **🟠 System Admin** - System management and configuration
3. **🟡 M&E Officer** - Monitoring & Evaluation with full county access
4. **🟢 Health Supervisor** - CHW management for assigned counties
5. **🔵 County Manager** - County-level health management
6. **🟣 Data Analyst** - Analysis and reporting capabilities
7. **⚪ Viewer** - Read-only access to assigned data
8. **⚫ Guest** - Limited read-only access

### Permission Matrix

| Permission | Super Admin | System Admin | M&E Officer | Health Supervisor | County Manager | Data Analyst | Viewer | Guest |
|------------|-------------|--------------|-------------|-------------------|----------------|--------------|--------|-------|
| **System Management** |
| Manage Users | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Manage Roles | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| System Config | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| View Audit Logs | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Data Access** |
| View All Counties | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ |
| View Assigned Counties | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| View Sensitive Data | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| Export Data | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ |
| **Analysis & Reporting** |
| Run Analysis | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| Create Reports | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Schedule Reports | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| View Performance Metrics | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **CHW Management** |
| Manage CHW Data | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| View CHW Performance | ✅ | ❌ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Assign CHW Supervisors | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **System Operations** |
| Cache Management | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Performance Monitoring | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Database Access | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

## 🔑 Authentication System

### Login Process

1. **User Credentials**: Username and password validation
2. **Account Status Check**: Active account verification
3. **Failed Attempt Tracking**: Automatic account lockout after 3 failed attempts
4. **Session Creation**: Secure session token generation
5. **Audit Logging**: All login attempts logged

### Session Management

- **Session Timeout**: 1 hour (configurable)
- **Secure Tokens**: Cryptographically secure session IDs
- **IP Tracking**: Session tied to IP address
- **Automatic Cleanup**: Expired sessions automatically removed

### Security Features

- **Password Hashing**: PBKDF2 with SHA-256 (100,000 iterations)
- **Salt Generation**: Unique salt per password
- **Account Lockout**: 15-minute lockout after failed attempts
- **Audit Trail**: Comprehensive security event logging

## 🏛️ County-Based Access Control

### Access Levels

1. **Global Access**: Super Admin, System Admin, M&E Officer, Data Analyst
2. **Assigned Counties Only**: Health Supervisor, County Manager, Viewer, Guest

### County Filtering

- **Automatic Query Filtering**: Queries automatically filtered by county access
- **Data Isolation**: Users can only see data from assigned counties
- **Cross-County Analysis**: Only permitted for global access roles

### County Assignments

```python
# Example county assignments
{
    "me_officer": ["Kisumu", "Busia", "Vihiga"],      # All counties
    "supervisor_kisumu": ["Kisumu"],                   # Single county
    "manager_western": ["Busia", "Vihiga"],           # Multiple counties
    "viewer_busia": ["Busia"]                         # Single county
}
```

## 🛡️ Implementation Details

### Environment Configuration

```bash
# RBAC Configuration in .env
RBAC_ENABLED=true
RBAC_STRICT_MODE=true
RBAC_SESSION_TIMEOUT=3600
RBAC_MAX_LOGIN_ATTEMPTS=3
RBAC_LOCKOUT_DURATION=900

# Default Admin Credentials (Change in production!)
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=KenyaHealth2025!
DEFAULT_ADMIN_EMAIL=admin@kenya-health-ai.com
```

### Database Files

- **RBAC Database**: `security/rbac.db`
- **Audit Log**: `security/rbac_audit.log`
- **Backup Enabled**: Automatic database backups

### Code Integration

```python
# Protecting functions with decorators
@require_permission(Permission.RUN_ANALYSIS)
def run_analysis():
    # Function implementation
    pass

@require_role([UserRole.SUPER_ADMIN, UserRole.SYSTEM_ADMIN])
def admin_function():
    # Admin-only function
    pass

@protected_page(title="Dashboard", required_permissions=[Permission.VIEW_ASSIGNED_COUNTIES])
def show_dashboard():
    # Protected Streamlit page
    pass
```

## 🧪 Testing and Validation

### Test Users Created

| Username | Role | Counties | Password |
|----------|------|----------|----------|
| `admin` | Super Admin | All | `KenyaHealth2025!` |
| `me_officer_test` | M&E Officer | All | `TestPass123!` |
| `supervisor_test` | Health Supervisor | Kisumu | `TestPass123!` |
| `viewer_test` | Viewer | Busia | `TestPass123!` |

### Test Results

✅ **All tests passed:**
- User creation and management
- Authentication and session management
- Role-based permission checking
- County-based access control
- Audit logging
- Session cleanup

### Running Tests

```bash
# Run RBAC system tests
python test_rbac.py

# Test Streamlit integration
streamlit run app/main_streamlit_app.py
```

## 🔧 User Management

### Admin Interface

Access via: **User Management** button (Admin only)

**Features:**
- Create new users
- Manage user roles and permissions
- View audit logs
- Reset passwords
- Activate/deactivate accounts
- View system statistics

### User Creation

```python
# Programmatic user creation
rbac = get_rbac_manager()
rbac.create_user(
    username="new_user",
    email="user@example.com",
    password="SecurePass123!",
    full_name="New User",
    role=UserRole.VIEWER,
    counties=["Kisumu"]
)
```

## 📊 Monitoring and Auditing

### Audit Events Tracked

- **LOGIN_SUCCESS**: Successful user login
- **LOGIN_FAILED**: Failed login attempt
- **USER_CREATED**: New user account creation
- **LOGOUT**: User logout
- **PERMISSION_DENIED**: Access denied events
- **DATA_ACCESS**: Data access attempts

### Audit Log Format

```json
{
    "timestamp": "2025-07-15 06:39:10",
    "user_id": "user123",
    "action": "LOGIN_SUCCESS",
    "resource": "user:admin",
    "details": "Successful login",
    "ip_address": "127.0.0.1",
    "success": true
}
```

### Security Monitoring

- **Failed Login Tracking**: Monitor brute force attempts
- **Session Monitoring**: Track active sessions
- **Permission Violations**: Log unauthorized access attempts
- **Data Export Tracking**: Monitor sensitive data exports

## 🚀 Deployment Considerations

### Production Security

1. **Change Default Passwords**: Update admin credentials
2. **Enable HTTPS**: Secure session cookies
3. **Database Encryption**: Encrypt RBAC database
4. **Regular Backups**: Backup user and audit data
5. **Session Security**: Configure secure session settings

### Environment Variables

```bash
# Production settings
APP_ENV=production
RBAC_STRICT_MODE=true
SESSION_COOKIE_SECURE=true
DATA_ENCRYPTION_ENABLED=true
AUDIT_LOGGING=true
```

### Maintenance Tasks

```bash
# Clean expired sessions
python -c "from security.rbac import get_rbac_manager; get_rbac_manager().cleanup_expired_sessions()"

# View audit statistics
python cache_manager.py stats

# Reset failed login attempts
python test_rbac.py
```

## 🔒 Security Best Practices

### Password Policy

- **Minimum Length**: 8 characters
- **Complexity**: Letters, numbers, special characters
- **Regular Updates**: Encourage password changes
- **No Reuse**: Prevent password reuse

### Session Security

- **Timeout**: Automatic session expiration
- **IP Binding**: Sessions tied to IP addresses
- **Secure Cookies**: HTTPOnly and Secure flags
- **CSRF Protection**: Cross-site request forgery protection

### Data Protection

- **Encryption at Rest**: Database encryption
- **Encryption in Transit**: HTTPS/TLS
- **Access Logging**: All data access logged
- **Data Minimization**: Only necessary data exposed

## 📞 Support and Troubleshooting

### Common Issues

1. **Login Failures**: Check account status and password
2. **Permission Denied**: Verify role assignments
3. **County Access**: Check county assignments
4. **Session Expired**: Re-login required

### Debug Commands

```bash
# Check user status
python -c "from security.rbac import get_rbac_manager; print(get_rbac_manager().user_exists('username'))"

# View user permissions
python test_rbac.py

# Check audit logs
sqlite3 security/rbac.db "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 10;"
```

---

**Security Status**: ✅ **IMPLEMENTED AND TESTED**

**Last Updated**: 2025-07-15

**RBAC System**: Fully operational with comprehensive testing completed
