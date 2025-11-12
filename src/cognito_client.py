"""
Cognito User Pool client for user management.
Handles user registration, authentication, and management through AWS Cognito.
"""
import os
import boto3
from botocore.exceptions import ClientError
from typing import Optional, List, Dict
from datetime import datetime, UTC


class CognitoClient:
    """Client for managing users in AWS Cognito User Pool."""
    
    def __init__(self, region: str, user_pool_id: str, app_client_id: str):
        self.region = region
        self.user_pool_id = user_pool_id
        self.app_client_id = app_client_id
        self.client = boto3.client('cognito-idp', region_name=region)
    
    def create_user(self, email: str, name: str, password: str, role: str = "USER") -> Dict:
        """
        Create a new user in Cognito User Pool.
        
        Args:
            email: User email
            name: User's full name
            password: User password
            role: User role (USER or ADMIN)
            
        Returns:
            Dict with user_id, email, name, role
        """
        try:
            # Create user with temporary password (they'll need to change it on first login)
            # Or create with permanent password if allowed
            response = self.client.admin_create_user(
                UserPoolId=self.user_pool_id,
                Username=email,
                UserAttributes=[
                    {'Name': 'email', 'Value': email},
                    {'Name': 'email_verified', 'Value': 'true'},
                    {'Name': 'name', 'Value': name},
                    {'Name': 'custom:role', 'Value': role.upper()},
                ],
                TemporaryPassword=password,
                MessageAction='SUPPRESS',  # Suppress welcome email
                DesiredDeliveryMediums=['EMAIL']
            )
            
            # Set permanent password
            try:
                self.client.admin_set_user_password(
                    UserPoolId=self.user_pool_id,
                    Username=email,
                    Password=password,
                    Permanent=True
                )
            except ClientError as e:
                # If password policy doesn't allow setting permanent password directly,
                # user will need to change password on first login
                print(f"Warning: Could not set permanent password: {e}")
            
            # Add user to group based on role
            group_name = "admin" if role.upper() == "ADMIN" else "user"
            try:
                self.client.admin_add_user_to_group(
                    UserPoolId=self.user_pool_id,
                    Username=email,
                    GroupName=group_name
                )
            except ClientError as e:
                # Group might not exist, create it
                if e.response['Error']['Code'] == 'ResourceNotFoundException':
                    self._create_group_if_not_exists(group_name)
                    self.client.admin_add_user_to_group(
                        UserPoolId=self.user_pool_id,
                        Username=email,
                        GroupName=group_name
                    )
                else:
                    print(f"Warning: Could not add user to group: {e}")
            
            user_id = response['User']['Username']
            created_at = response['User'].get('UserCreateDate', datetime.now(UTC)).isoformat()
            
            return {
                'user_id': user_id,
                'email': email,
                'name': name,
                'role': role.upper(),
                'created_at': created_at
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'UsernameExistsException':
                raise ValueError("Email already exists")
            elif error_code == 'InvalidPasswordException':
                raise ValueError(f"Password does not meet requirements: {e.response['Error']['Message']}")
            else:
                raise Exception(f"Failed to create user: {e.response['Error']['Message']}")
    
    def authenticate_user(self, email: str, password: str) -> Dict:
        """
        Authenticate user and return tokens.
        
        Args:
            email: User email
            password: User password
            
        Returns:
            Dict with tokens and user information
        """
        try:
            # Use AdminInitiateAuth for server-side authentication
            response = self.client.admin_initiate_auth(
                UserPoolId=self.user_pool_id,
                ClientId=self.app_client_id,
                AuthFlow='ADMIN_NO_SRP_AUTH',
                AuthParameters={
                    'USERNAME': email,
                    'PASSWORD': password,
                }
            )
            
            # Check if new password required (first login)
            if response.get('ChallengeName') == 'NEW_PASSWORD_REQUIRED':
                # User needs to set a new password
                raise ValueError("New password required. Please use change password endpoint.")
            
            # Get tokens
            auth_result = response.get('AuthenticationResult', {})
            id_token = auth_result.get('IdToken')
            
            if not id_token:
                raise ValueError("Authentication failed: No token returned")
            
            # Get user details to extract role
            user_info = self.get_user_by_email(email)
            
            return {
                'token': id_token,  # Return ID token for JWT verification
                'user_id': user_info['user_id'],
                'role': user_info['role'],
                'email': email,
                'name': user_info['name']
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code in ['NotAuthorizedException', 'UserNotFoundException']:
                raise ValueError("Invalid credentials")
            elif error_code == 'PasswordResetRequiredException':
                raise ValueError("Password reset required")
            else:
                raise Exception(f"Authentication failed: {e.response['Error']['Message']}")
    
    def get_user_by_email(self, email: str) -> Dict:
        """
        Get user information by email.
        
        Args:
            email: User email
            
        Returns:
            Dict with user information
        """
        try:
            response = self.client.admin_get_user(
                UserPoolId=self.user_pool_id,
                Username=email
            )
            
            # Extract attributes
            attributes = {attr['Name']: attr['Value'] for attr in response.get('UserAttributes', [])}
            
            # Get user groups to determine role
            groups_response = self.client.admin_list_groups_for_user(
                UserPoolId=self.user_pool_id,
                Username=email
            )
            groups = [g['GroupName'] for g in groups_response.get('Groups', [])]
            
            # Determine role from groups or custom attribute
            role = attributes.get('custom:role', 'USER')
            if 'admin' in groups:
                role = 'ADMIN'
            elif 'user' in groups or not groups:
                role = 'USER'
            
            return {
                'user_id': response['Username'],
                'email': attributes.get('email', email),
                'name': attributes.get('name', ''),
                'role': role.upper(),
                'created_at': response.get('UserCreateDate', datetime.now(UTC)).isoformat(),
                'enabled': response.get('Enabled', True)
            }
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'UserNotFoundException':
                return None
            raise Exception(f"Failed to get user: {e.response['Error']['Message']}")
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """
        Get user information by user ID (username).
        
        Args:
            user_id: User ID (Cognito username)
            
        Returns:
            Dict with user information or None if not found
        """
        try:
            response = self.client.admin_get_user(
                UserPoolId=self.user_pool_id,
                Username=user_id
            )
            
            attributes = {attr['Name']: attr['Value'] for attr in response.get('UserAttributes', [])}
            
            # Get user groups
            groups_response = self.client.admin_list_groups_for_user(
                UserPoolId=self.user_pool_id,
                Username=user_id
            )
            groups = [g['GroupName'] for g in groups_response.get('Groups', [])]
            
            role = attributes.get('custom:role', 'USER')
            if 'ADMIN' in groups:
                role = 'ADMIN'
            elif 'USER' in groups or not groups:
                role = 'USER'
            
            return {
                'user_id': response['Username'],
                'email': attributes.get('email', user_id),
                'name': attributes.get('preferred_username', ''),
                'role': role.upper(),
                'created_at': response.get('UserCreateDate', datetime.now(UTC)).isoformat(),
                'enabled': response.get('Enabled', True)
            }
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'UserNotFoundException':
                return None
            raise Exception(f"Failed to get user: {e.response['Error']['Message']}")
    
    def update_user(self, email: str, name: Optional[str] = None, 
                   password: Optional[str] = None, role: Optional[str] = None) -> bool:
        """
        Update user attributes.
        
        Args:
            email: User email
            name: New name (optional)
            password: New password (optional)
            role: New role (optional)
            
        Returns:
            True if successful
        """
        try:
            # Update attributes
            attributes = []
            if name:
                attributes.append({'Name': 'name', 'Value': name})
            if role:
                attributes.append({'Name': 'custom:role', 'Value': role.upper()})
            
            if attributes:
                self.client.admin_update_user_attributes(
                    UserPoolId=self.user_pool_id,
                    Username=email,
                    UserAttributes=attributes
                )
            
            # Update password if provided
            if password:
                self.client.admin_set_user_password(
                    UserPoolId=self.user_pool_id,
                    Username=email,
                    Password=password,
                    Permanent=True
                )
            
            # Update groups if role changed
            if role:
                # Remove from all groups
                groups_response = self.client.admin_list_groups_for_user(
                    UserPoolId=self.user_pool_id,
                    Username=email
                )
                for group in groups_response.get('Groups', []):
                    self.client.admin_remove_user_from_group(
                        UserPoolId=self.user_pool_id,
                        Username=email,
                        GroupName=group['GroupName']
                    )
                
                # Add to new group
                group_name = "admin" if role.upper() == "ADMIN" else "user"
                self._create_group_if_not_exists(group_name)
                self.client.admin_add_user_to_group(
                    UserPoolId=self.user_pool_id,
                    Username=email,
                    GroupName=group_name
                )
            
            return True
            
        except ClientError as e:
            raise Exception(f"Failed to update user: {e.response['Error']['Message']}")
    
    def delete_user(self, email: str) -> bool:
        """
        Delete user from Cognito User Pool.
        
        Args:
            email: User email
            
        Returns:
            True if successful
        """
        try:
            self.client.admin_delete_user(
                UserPoolId=self.user_pool_id,
                Username=email
            )
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == 'UserNotFoundException':
                return False
            raise Exception(f"Failed to delete user: {e.response['Error']['Message']}")
    
    def list_users(self, limit: int = 60) -> List[Dict]:
        """
        List all users in the User Pool.
        
        Args:
            limit: Maximum number of users to return
            
        Returns:
            List of user dictionaries
        """
        try:
            users = []
            pagination_token = None
            
            while True:
                params = {
                    'UserPoolId': self.user_pool_id,
                    'Limit': min(limit, 60)  # Cognito max is 60
                }
                if pagination_token:
                    params['PaginationToken'] = pagination_token
                
                response = self.client.list_users(**params)
                
                for user in response.get('Users', []):
                    attributes = {attr['Name']: attr['Value'] for attr in user.get('Attributes', [])}
                    
                    # Get user groups
                    try:
                        groups_response = self.client.admin_list_groups_for_user(
                            UserPoolId=self.user_pool_id,
                            Username=user['Username']
                        )
                        groups = [g['GroupName'] for g in groups_response.get('Groups', [])]
                    except:
                        groups = []
                    
                    role = attributes.get('custom:role', 'USER')
                    if 'ADMIN' in groups:
                        role = 'ADMIN'
                    elif 'USER' in groups or not groups:
                        role = 'USER'
                    
                    users.append({
                        'user_id': user['Username'],
                        'email': attributes.get('email', user['Username']),
                        'name': attributes.get('preferred_username', ''),
                        'role': role.upper(),
                        'created_at': user.get('UserCreateDate', datetime.now(UTC)).isoformat(),
                        'enabled': user.get('Enabled', True)
                    })
                
                pagination_token = response.get('PaginationToken')
                if not pagination_token or len(users) >= limit:
                    break
            
            return users[:limit]
            
        except ClientError as e:
            raise Exception(f"Failed to list users: {e.response['Error']['Message']}")
    
    def count_users(self) -> int:
        """
        Get total number of users in the User Pool.
        
        Returns:
            Number of users
        """
        try:
            # List all users and count them
            # Note: For better performance in production, consider using CloudWatch metrics
            users = self.list_users(limit=10000)  # Large limit to get all users
            return len(users)
        except ClientError:
            # Fallback: return -1 to indicate error
            return -1
        except Exception:
            return -1
    
    def _create_group_if_not_exists(self, group_name: str):
        """Create a Cognito group if it doesn't exist."""
        try:
            self.client.create_group(
                GroupName=group_name,
                UserPoolId=self.user_pool_id,
                Description=f"{group_name.title()} group"
            )
        except ClientError as e:
            if e.response['Error']['Code'] != 'ResourceAlreadyExistsException':
                raise


def build_cognito_client() -> Optional[CognitoClient]:
    """
    Build CognitoClient from environment variables.
    
    Returns:
        CognitoClient instance or None if not configured
    """
    region = os.getenv("COGNITO_REGION") or os.getenv("AWS_REGION")
    user_pool_id = os.getenv("COGNITO_USER_POOL_ID")
    app_client_id = os.getenv("COGNITO_APP_CLIENT_ID")
    
    if not (region and user_pool_id and app_client_id):
        return None
    
    return CognitoClient(region, user_pool_id, app_client_id)