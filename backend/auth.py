"""JWT authentication middleware for FastAPI."""
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from navy_agent_mvp.config import get_supabase_client

security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    """
    Verify Supabase JWT token and return the decoded payload.
    
    Args:
        credentials: HTTP Authorization header with Bearer token
        
    Returns:
        dict: Decoded JWT payload with user info
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    token = credentials.credentials
    
    try:
        supabase = get_supabase_client()
        user_response = supabase.auth.get_user(token)
        user = getattr(user_response, "user", None)
        user_id = getattr(user, "id", None)
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")

        return {
            "sub": user_id,
            "email": getattr(user, "email", None),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")

def get_user_id(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    """
    Extract user ID from JWT token.
    
    Args:
        credentials: HTTP Authorization header with Bearer token
        
    Returns:
        str: User ID (UUID)
    """
    payload = verify_token(credentials)
    user_id = payload.get("sub")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found in token")
    
    return user_id


def get_auth_context(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    """
    Return authenticated request context.

    Includes:
    - user_id: Supabase auth user id
    - access_token: bearer token from request
    """
    user_id = get_user_id(credentials)
    return {
        "user_id": user_id,
        "access_token": credentials.credentials,
    }
