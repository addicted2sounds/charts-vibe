import boto3
import json
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)

class SSMCredentialsManager:
    """Manager for Google OAuth2 credentials stored in AWS SSM Parameter Store"""
    
    def __init__(self, ssm_prefix="/ytmusic-playlist-app", region_name=None):
        """
        Initialize the credentials manager
        
        Args:
            ssm_prefix: Prefix for SSM parameter names
            region_name: AWS region name (if None, uses default region)
        """
        self.ssm_prefix = ssm_prefix
        self.ssm_client = boto3.client('ssm', region_name=region_name)
        
    def get_google_oauth_config(self):
        """
        Retrieve Google OAuth2 configuration from SSM Parameter Store
        
        Returns:
            dict: Configuration dictionary in the same format as client_secret.json
            
        Raises:
            Exception: If parameters cannot be retrieved from SSM
        """
        try:
            # Get all parameters with the prefix
            parameter_names = [
                f"{self.ssm_prefix}/client_id",
                f"{self.ssm_prefix}/client_secret", 
                f"{self.ssm_prefix}/project_id",
                f"{self.ssm_prefix}/auth_uri",
                f"{self.ssm_prefix}/token_uri",
                f"{self.ssm_prefix}/auth_provider_x509_cert_url",
                f"{self.ssm_prefix}/redirect_uris"
            ]
            
            # Get parameters from SSM
            response = self.ssm_client.get_parameters(
                Names=parameter_names,
                WithDecryption=True  # Required for SecureString parameters
            )
            
            if response['InvalidParameters']:
                missing_params = response['InvalidParameters']
                raise Exception(f"Missing SSM parameters: {missing_params}")
            
            # Convert response to dictionary
            params = {}
            for param in response['Parameters']:
                key = param['Name'].replace(f"{self.ssm_prefix}/", "")
                params[key] = param['Value']
            
            # Convert redirect_uris back to list
            redirect_uris = params['redirect_uris'].split(',') if params.get('redirect_uris') else []
            
            # Build config in the same format as client_secret.json
            config = {
                "installed": {
                    "client_id": params['client_id'],
                    "project_id": params['project_id'],
                    "auth_uri": params['auth_uri'],
                    "token_uri": params['token_uri'],
                    "auth_provider_x509_cert_url": params['auth_provider_x509_cert_url'],
                    "client_secret": params['client_secret'],
                    "redirect_uris": redirect_uris
                }
            }
            
            logger.info("Successfully retrieved Google OAuth2 config from SSM")
            return config
            
        except ClientError as e:
            logger.error(f"AWS SSM error: {e}")
            raise Exception(f"Failed to retrieve credentials from SSM: {e}")
        except Exception as e:
            logger.error(f"Error retrieving OAuth config: {e}")
            raise
    
    def get_parameter(self, parameter_name, decrypt=True):
        """
        Get a single parameter from SSM
        
        Args:
            parameter_name: Name of the parameter (without prefix)
            decrypt: Whether to decrypt SecureString parameters
            
        Returns:
            str: Parameter value
        """
        try:
            full_name = f"{self.ssm_prefix}/{parameter_name}"
            response = self.ssm_client.get_parameter(
                Name=full_name,
                WithDecryption=decrypt
            )
            return response['Parameter']['Value']
        except ClientError as e:
            logger.error(f"Failed to get parameter {parameter_name}: {e}")
            raise
    
    def test_connection(self):
        """
        Test if SSM parameters are accessible
        
        Returns:
            bool: True if parameters can be retrieved
        """
        try:
            self.get_parameter('project_id', decrypt=False)
            return True
        except Exception:
            return False

# Convenience function for backward compatibility
def get_google_oauth_config(ssm_prefix="/ytmusic-playlist-app", region_name=None):
    """
    Convenience function to get Google OAuth2 config from SSM
    
    Args:
        ssm_prefix: SSM parameter prefix
        region_name: AWS region name
        
    Returns:
        dict: Google OAuth2 configuration
    """
    manager = SSMCredentialsManager(ssm_prefix, region_name)
    return manager.get_google_oauth_config()

if __name__ == "__main__":
    # Test the credentials manager
    try:
        manager = SSMCredentialsManager()
        
        if not manager.test_connection():
            print("❌ Cannot connect to SSM or parameters don't exist")
            print("Make sure to run bin/setup-ssm-parameters.sh first")
            exit(1)
            
        config = manager.get_google_oauth_config()
        print("✅ Successfully retrieved OAuth config from SSM")
        print(f"Project ID: {config['installed']['project_id']}")
        print(f"Client ID: {config['installed']['client_id'][:20]}...")
        print(f"Redirect URIs: {config['installed']['redirect_uris']}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        exit(1)
