"""
Input Sanitization Utilities
Functions for sanitizing user input to prevent injection attacks
"""

import re
from typing import Optional


def sanitize_search_query(query: Optional[str], max_length: int = 100) -> Optional[str]:
    """
    Sanitize search query input
    
    - Removes potentially dangerous characters
    - Limits length to prevent DoS
    - Strips whitespace
    """
    if not query:
        return None

    # Strip whitespace
    query = query.strip()

    # Limit length
    if len(query) > max_length:
        query = query[:max_length]

    # Remove potentially dangerous characters for SQL injection
    # Note: SQLAlchemy parameterized queries already prevent SQL injection
    # This is an additional layer of defense
    dangerous_patterns = [
        r';.*--',           # SQL comment injection
        r'union\s+select',  # UNION injection
        r'exec\s*\(',       # Stored procedure execution
        r'xp_cmdshell',     # Command shell execution
        r'<script',         # XSS prevention
        r'javascript:',     # JavaScript protocol
        r'on\w+\s*=',       # Event handlers
    ]

    for pattern in dangerous_patterns:
        query = re.sub(pattern, '', query, flags=re.IGNORECASE)

    return query if query else None


def sanitize_phone(phone: Optional[str]) -> Optional[str]:
    """
    Sanitize phone number - keep only digits and common separators
    """
    if not phone:
        return None

    # Keep only digits, spaces, dashes, parentheses, and plus
    phone = re.sub(r'[^\d\s\-\(\)\+]', '', phone)

    return phone.strip() if phone else None


def sanitize_email(email: Optional[str]) -> Optional[str]:
    """
    Sanitize email address
    """
    if not email:
        return None

    # Convert to lowercase and strip whitespace
    email = email.lower().strip()

    # Basic email format validation
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        return None

    return email


def sanitize_name(name: Optional[str], max_length: int = 100) -> Optional[str]:
    """
    Sanitize name fields
    """
    if not name:
        return None

    # Strip whitespace
    name = name.strip()

    # Limit length
    if len(name) > max_length:
        name = name[:max_length]

    # Remove any HTML/script tags
    name = re.sub(r'<[^>]+>', '', name)

    return name if name else None


def sanitize_id(id_value: Optional[str]) -> Optional[str]:
    """
    Sanitize ID fields - should only contain alphanumeric characters and dashes
    """
    if not id_value:
        return None

    # Only allow alphanumeric, dashes, and underscores
    id_value = re.sub(r'[^a-zA-Z0-9\-_]', '', id_value)

    return id_value if id_value else None