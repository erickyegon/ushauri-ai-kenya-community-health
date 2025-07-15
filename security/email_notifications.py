"""
Email Notification System for Ushauri AI
Handles access requests and user notifications
"""

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class EmailNotificationService:
    """Email notification service for access requests and user management"""
    
    def __init__(self):
        self.smtp_host = os.getenv('EMAIL_SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('EMAIL_SMTP_PORT', 587))
        self.username = os.getenv('EMAIL_USERNAME', '')
        self.password = os.getenv('EMAIL_PASSWORD', '')
        self.use_tls = os.getenv('EMAIL_USE_TLS', 'true').lower() == 'true'
        self.from_address = os.getenv('EMAIL_FROM_ADDRESS', self.username)
        self.admin_address = os.getenv('EMAIL_ADMIN_ADDRESS', 'keyegon@gmail.com')
        self.enabled = os.getenv('EMAIL_ENABLED', 'false').lower() == 'true'
    
    def send_email(self, to_address: str, subject: str, body: str, html_body: str = None) -> bool:
        """Send email notification"""
        if not self.enabled:
            logger.info(f"Email disabled - would send: {subject} to {to_address}")
            return True
        
        if not self.username or not self.password:
            logger.error("Email credentials not configured")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.from_address
            msg['To'] = to_address
            msg['Subject'] = subject
            
            # Add text part
            text_part = MIMEText(body, 'plain')
            msg.attach(text_part)
            
            # Add HTML part if provided
            if html_body:
                html_part = MIMEText(html_body, 'html')
                msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {to_address}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_address}: {e}")
            return False
    
    def send_access_request_notification(self, request_data: Dict) -> bool:
        """Send access request notification to admin"""
        subject = f"🔐 Ushauri AI - New Access Request from {request_data['full_name']}"
        
        # Text version
        text_body = f"""
New Access Request for Ushauri AI - Kenya Community Health Systems

Request Details:
================
Full Name: {request_data['full_name']}
Email: {request_data['email']}
Organization: {request_data['organization']}
Role Requested: {request_data['role_requested']}
Counties: {', '.join(request_data['counties']) if request_data['counties'] else 'None specified'}

Justification:
{request_data['justification']}

Request Submitted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

To approve this request:
1. Log into the Ushauri AI system as admin
2. Go to User Management
3. Create a new user with the above details

System: Ushauri AI - Kenya Community Health Systems
Admin Panel: http://localhost:8501
        """
        
        # HTML version
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2c5aa0; border-bottom: 2px solid #2c5aa0; padding-bottom: 10px;">
                    🔐 New Access Request - Ushauri AI
                </h2>
                
                <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="color: #495057; margin-top: 0;">Request Details</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px; font-weight: bold; width: 30%;">Full Name:</td>
                            <td style="padding: 8px;">{request_data['full_name']}</td>
                        </tr>
                        <tr style="background-color: #ffffff;">
                            <td style="padding: 8px; font-weight: bold;">Email:</td>
                            <td style="padding: 8px;">{request_data['email']}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; font-weight: bold;">Organization:</td>
                            <td style="padding: 8px;">{request_data['organization']}</td>
                        </tr>
                        <tr style="background-color: #ffffff;">
                            <td style="padding: 8px; font-weight: bold;">Role Requested:</td>
                            <td style="padding: 8px;">{request_data['role_requested']}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; font-weight: bold;">Counties:</td>
                            <td style="padding: 8px;">{', '.join(request_data['counties']) if request_data['counties'] else 'None specified'}</td>
                        </tr>
                    </table>
                </div>
                
                <div style="background-color: #e9ecef; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <h4 style="color: #495057; margin-top: 0;">Justification:</h4>
                    <p style="margin: 0; font-style: italic;">{request_data['justification']}</p>
                </div>
                
                <div style="background-color: #d4edda; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #28a745;">
                    <h4 style="color: #155724; margin-top: 0;">To Approve This Request:</h4>
                    <ol style="margin: 0; color: #155724;">
                        <li>Log into the Ushauri AI system as admin</li>
                        <li>Go to User Management</li>
                        <li>Create a new user with the above details</li>
                    </ol>
                </div>
                
                <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #dee2e6;">
                    <p style="color: #6c757d; font-size: 14px; margin: 0;">
                        <strong>Ushauri AI - Kenya Community Health Systems</strong><br>
                        Request submitted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>
                        Admin Panel: <a href="http://localhost:8501" style="color: #2c5aa0;">http://localhost:8501</a>
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(self.admin_address, subject, text_body, html_body)
    
    def send_access_approved_notification(self, user_data: Dict, temp_password: str) -> bool:
        """Send access approved notification to user"""
        subject = f"✅ Ushauri AI - Access Approved for {user_data['full_name']}"
        
        # Text version
        text_body = f"""
Welcome to Ushauri AI - Kenya Community Health Systems!

Your access request has been approved. Here are your login credentials:

Login Details:
==============
Username: {user_data['username']}
Temporary Password: {temp_password}
Role: {user_data['role']}
Assigned Counties: {', '.join(user_data['counties']) if user_data['counties'] else 'All counties'}

System Access:
==============
URL: http://localhost:8501
Login: Use the credentials above

IMPORTANT SECURITY NOTICE:
- Please change your password immediately after first login
- Do not share your credentials with anyone
- Log out when finished using the system

If you have any questions or need assistance, please contact the system administrator.

Welcome to the team!

Ushauri AI - Kenya Community Health Systems
        """
        
        # HTML version
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #28a745; border-bottom: 2px solid #28a745; padding-bottom: 10px;">
                    ✅ Welcome to Ushauri AI!
                </h2>
                
                <p style="font-size: 16px; color: #495057;">
                    Congratulations! Your access request has been approved.
                </p>
                
                <div style="background-color: #d4edda; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #28a745;">
                    <h3 style="color: #155724; margin-top: 0;">Login Credentials</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px; font-weight: bold; width: 30%;">Username:</td>
                            <td style="padding: 8px; font-family: monospace; background-color: #f8f9fa; border-radius: 4px;">{user_data['username']}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; font-weight: bold;">Password:</td>
                            <td style="padding: 8px; font-family: monospace; background-color: #f8f9fa; border-radius: 4px;">{temp_password}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; font-weight: bold;">Role:</td>
                            <td style="padding: 8px;">{user_data['role']}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; font-weight: bold;">Counties:</td>
                            <td style="padding: 8px;">{', '.join(user_data['counties']) if user_data['counties'] else 'All counties'}</td>
                        </tr>
                    </table>
                </div>
                
                <div style="background-color: #f8f9fa; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <h4 style="color: #495057; margin-top: 0;">System Access</h4>
                    <p style="margin: 0;">
                        <strong>URL:</strong> <a href="http://localhost:8501" style="color: #2c5aa0;">http://localhost:8501</a><br>
                        <strong>Login:</strong> Use the credentials above
                    </p>
                </div>
                
                <div style="background-color: #fff3cd; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #ffc107;">
                    <h4 style="color: #856404; margin-top: 0;">🔒 Important Security Notice</h4>
                    <ul style="margin: 0; color: #856404;">
                        <li>Please change your password immediately after first login</li>
                        <li>Do not share your credentials with anyone</li>
                        <li>Log out when finished using the system</li>
                    </ul>
                </div>
                
                <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #dee2e6;">
                    <p style="color: #6c757d; font-size: 14px; margin: 0;">
                        <strong>Ushauri AI - Kenya Community Health Systems</strong><br>
                        If you have questions, contact the system administrator<br>
                        Welcome to the team! 🎉
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(user_data['email'], subject, text_body, html_body)

# Global email service instance
_email_service = None

def get_email_service() -> EmailNotificationService:
    """Get global email service instance"""
    global _email_service
    if _email_service is None:
        _email_service = EmailNotificationService()
    return _email_service

def send_access_request_email(request_data: Dict) -> bool:
    """Send access request notification email"""
    email_service = get_email_service()
    return email_service.send_access_request_notification(request_data)

def send_access_approved_email(user_data: Dict, temp_password: str) -> bool:
    """Send access approved notification email"""
    email_service = get_email_service()
    return email_service.send_access_approved_notification(user_data, temp_password)
