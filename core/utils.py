import os
import logging
import re
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from .schemas import FileUpload

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('hospital_management.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class FileHandler:
    ALLOWED_EXTENSIONS = {
        'image/jpeg': '.jpg',
        'image/png': '.png',
        'application/pdf': '.pdf'
    }
    
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
    
    @staticmethod
    def validate_file(file, file_data: FileUpload) -> Tuple[bool, str]:
        """
        Validate file before saving
        """
        try:
            # Check file size
            if file.size > FileHandler.MAX_FILE_SIZE:
                return False, f"File size exceeds maximum limit of {FileHandler.MAX_FILE_SIZE/1024/1024}MB"
            
            # Validate file type
            if file_data.file_type not in FileHandler.ALLOWED_EXTENSIONS:
                return False, f"Unsupported file type: {file_data.file_type}"
            
            # Validate file name
            if not re.match(r'^[a-zA-Z0-9_-]+$', file_data.file_name):
                return False, "Invalid file name. Use only letters, numbers, underscores, and hyphens."
            
            return True, "File validation successful"
            
        except Exception as e:
            logger.error(f"File validation error: {str(e)}")
            return False, str(e)
    
    @staticmethod
    def save_file(file, file_data: FileUpload, directory: str) -> Tuple[bool, str]:
        """
        Save a file to the specified directory with proper error handling
        """
        try:
            # Validate file data
            file_data = FileUpload(**file_data)
            
            # Validate file
            is_valid, message = FileHandler.validate_file(file, file_data)
            if not is_valid:
                return False, message
            
            # Generate unique filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            extension = FileHandler.ALLOWED_EXTENSIONS.get(file_data.file_type)
            filename = f"{timestamp}_{file_data.file_name}{extension}"
            file_path = os.path.join(directory, filename)
            
            # Save file
            path = default_storage.save(file_path, ContentFile(file.read()))
            logger.info(f"File saved successfully: {path}")
            return True, path
            
        except Exception as e:
            logger.error(f"Error saving file: {str(e)}")
            return False, str(e)
    
    @staticmethod
    def delete_file(file_path: str) -> Tuple[bool, str]:
        """
        Delete a file with proper error handling
        """
        try:
            if default_storage.exists(file_path):
                default_storage.delete(file_path)
                logger.info(f"File deleted successfully: {file_path}")
                return True, "File deleted successfully"
            return False, "File not found"
        except Exception as e:
            logger.error(f"Error deleting file: {str(e)}")
            return False, str(e)

class ErrorHandler:
    ERROR_TYPES = {
        'ValidationError': 'Invalid input data',
        'PermissionDenied': 'Access denied',
        'DatabaseError': 'Database operation failed',
        'FileError': 'File operation failed',
        'AuthenticationError': 'Authentication failed',
        'RateLimitError': 'Too many requests',
    }
    
    @staticmethod
    def handle_error(error: Exception, context: Optional[str] = None) -> dict:
        """
        Handle and log errors with proper context
        """
        error_message = str(error)
        error_type = type(error).__name__
        
        # Get user-friendly message
        user_message = ErrorHandler.ERROR_TYPES.get(error_type, 'An unexpected error occurred')
        
        # Log the error with stack trace
        logger.error(
            f"Error in {context if context else 'unknown context'}: {error_type} - {error_message}",
            exc_info=True
        )
        
        # Return error response
        return {
            'status': 'error',
            'error_type': error_type,
            'message': user_message,
            'context': context,
            'timestamp': datetime.now().isoformat()
        }
    
    @staticmethod
    def validate_request_data(data: dict, required_fields: list) -> Tuple[bool, Optional[str]]:
        """
        Validate request data for required fields
        """
        try:
            # Check for missing fields
            missing_fields = [field for field in required_fields if not data.get(field)]
            if missing_fields:
                error_message = f"Missing required fields: {', '.join(missing_fields)}"
                logger.warning(error_message)
                return False, error_message
            
            # Validate field types and formats
            for field, value in data.items():
                if field == 'email' and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', value):
                    return False, "Invalid email format"
                elif field == 'phone' and not re.match(r'^[0-9]{10}$', value):
                    return False, "Invalid phone number format"
                elif field == 'date_of_birth':
                    try:
                        date = datetime.strptime(value, '%Y-%m-%d').date()
                        if date > datetime.now().date():
                            return False, "Date of birth cannot be in the future"
                    except ValueError:
                        return False, "Invalid date format. Use YYYY-MM-DD"
            
            return True, None
            
        except Exception as e:
            logger.error(f"Data validation error: {str(e)}")
            return False, str(e)

class DatabaseHandler:
    @staticmethod
    def safe_db_operation(operation_func, *args, **kwargs):
        """
        Safely execute database operations with proper error handling
        """
        try:
            return operation_func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Database operation failed: {str(e)}", exc_info=True)
            raise
    
    @staticmethod
    def get_or_none(model, **kwargs):
        """
        Safely get an object or return None
        """
        try:
            return model.objects.get(**kwargs)
        except model.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Error getting object: {str(e)}")
            return None

class SecurityHandler:
    PASSWORD_MIN_LENGTH = 8
    PASSWORD_MAX_LENGTH = 128
    
    @staticmethod
    def sanitize_input(data: str) -> str:
        """
        Sanitize user input to prevent XSS attacks
        """
        import html
        return html.escape(data.strip())
    
    @staticmethod
    def validate_password_strength(password: str) -> Tuple[bool, str]:
        """
        Validate password strength
        """
        if len(password) < SecurityHandler.PASSWORD_MIN_LENGTH:
            return False, f"Password must be at least {SecurityHandler.PASSWORD_MIN_LENGTH} characters long"
        if len(password) > SecurityHandler.PASSWORD_MAX_LENGTH:
            return False, f"Password must not exceed {SecurityHandler.PASSWORD_MAX_LENGTH} characters"
        if not any(c.isupper() for c in password):
            return False, "Password must contain at least one uppercase letter"
        if not any(c.islower() for c in password):
            return False, "Password must contain at least one lowercase letter"
        if not any(c.isdigit() for c in password):
            return False, "Password must contain at least one number"
        if not any(c in '!@#$%^&*(),.?":{}|<>' for c in password):
            return False, "Password must contain at least one special character"
        return True, "Password is strong"
    
    @staticmethod
    def generate_secure_token(length: int = 32) -> str:
        """
        Generate a secure random token
        """
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password using SHA-256
        """
        salt = secrets.token_hex(16)
        hash_obj = hashlib.sha256((password + salt).encode())
        return f"{salt}${hash_obj.hexdigest()}"
    
    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash
        """
        try:
            salt, hash_value = hashed_password.split('$')
            hash_obj = hashlib.sha256((password + salt).encode())
            return hash_obj.hexdigest() == hash_value
        except Exception:
            return False
    
    @staticmethod
    def validate_session(request) -> bool:
        """
        Validate user session
        """
        try:
            if not request.session.session_key:
                return False
            
            # Check session expiry
            if 'last_activity' in request.session:
                last_activity = datetime.fromisoformat(request.session['last_activity'])
                if datetime.now() - last_activity > timedelta(minutes=settings.SESSION_COOKIE_AGE):
                    return False
            
            # Update last activity
            request.session['last_activity'] = datetime.now().isoformat()
            return True
            
        except Exception as e:
            logger.error(f"Session validation error: {str(e)}")
            return False 