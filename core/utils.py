import os
import logging
from datetime import datetime
from typing import Optional, Tuple
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
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
    
    @staticmethod
    def save_file(file, file_data: FileUpload, directory: str) -> Tuple[bool, str]:
        """
        Save a file to the specified directory with proper error handling
        """
        try:
            # Validate file data
            file_data = FileUpload(**file_data)
            
            # Generate unique filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            extension = FileHandler.ALLOWED_EXTENSIONS.get(file_data.file_type)
            if not extension:
                raise ValueError(f"Unsupported file type: {file_data.file_type}")
            
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
    @staticmethod
    def handle_error(error: Exception, context: Optional[str] = None) -> dict:
        """
        Handle and log errors with proper context
        """
        error_message = str(error)
        error_type = type(error).__name__
        
        # Log the error
        logger.error(f"Error in {context if context else 'unknown context'}: {error_type} - {error_message}")
        
        # Return error response
        return {
            'status': 'error',
            'error_type': error_type,
            'message': error_message,
            'context': context
        }
    
    @staticmethod
    def validate_request_data(data: dict, required_fields: list) -> Tuple[bool, Optional[str]]:
        """
        Validate request data for required fields
        """
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            error_message = f"Missing required fields: {', '.join(missing_fields)}"
            logger.warning(error_message)
            return False, error_message
        return True, None

class DatabaseHandler:
    @staticmethod
    def safe_db_operation(operation_func, *args, **kwargs):
        """
        Safely execute database operations with proper error handling
        """
        try:
            return operation_func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Database operation failed: {str(e)}")
            raise

class SecurityHandler:
    @staticmethod
    def sanitize_input(data: str) -> str:
        """
        Sanitize user input to prevent XSS attacks
        """
        import html
        return html.escape(data)
    
    @staticmethod
    def validate_password_strength(password: str) -> Tuple[bool, str]:
        """
        Validate password strength
        """
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"
        if not any(c.isupper() for c in password):
            return False, "Password must contain at least one uppercase letter"
        if not any(c.islower() for c in password):
            return False, "Password must contain at least one lowercase letter"
        if not any(c.isdigit() for c in password):
            return False, "Password must contain at least one number"
        return True, "Password is strong" 