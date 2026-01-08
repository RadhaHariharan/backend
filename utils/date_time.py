"""
Date and time utility functions.
All datetime operations should use timezone-aware UTC timestamps.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional


def utc_now() -> datetime:
    """
    Get current UTC time as timezone-aware datetime.
    
    Returns:
        datetime: Current UTC time with timezone info
    """
    return datetime.now(timezone.utc)


def utc_from_timestamp(timestamp: float) -> datetime:
    """
    Convert Unix timestamp to timezone-aware UTC datetime.
    
    Args:
        timestamp: Unix timestamp (seconds since epoch)
        
    Returns:
        datetime: UTC datetime with timezone info
    """
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def to_utc(dt: datetime) -> datetime:
    """
    Convert any datetime to UTC timezone-aware datetime.
    
    Args:
        dt: Datetime object (naive or aware)
        
    Returns:
        datetime: UTC datetime with timezone info
    """
    if dt.tzinfo is None:
        # Naive datetime - assume it's UTC
        return dt.replace(tzinfo=timezone.utc)
    # Already aware - convert to UTC
    return dt.astimezone(timezone.utc)


def add_minutes(dt: datetime, minutes: int) -> datetime:
    """
    Add minutes to a datetime.
    
    Args:
        dt: Base datetime
        minutes: Number of minutes to add (can be negative)
        
    Returns:
        datetime: New datetime with minutes added
    """
    return dt + timedelta(minutes=minutes)


def add_days(dt: datetime, days: int) -> datetime:
    """
    Add days to a datetime.
    
    Args:
        dt: Base datetime
        days: Number of days to add (can be negative)
        
    Returns:
        datetime: New datetime with days added
    """
    return dt + timedelta(days=days)


def format_iso(dt: datetime) -> str:
    """
    Format datetime as ISO 8601 string.
    
    Args:
        dt: Datetime to format
        
    Returns:
        str: ISO formatted string (e.g., '2024-01-08T10:30:00+00:00')
    """
    return dt.isoformat()


def parse_iso(iso_string: str) -> Optional[datetime]:
    """
    Parse ISO 8601 datetime string.
    
    Args:
        iso_string: ISO formatted datetime string
        
    Returns:
        datetime: Parsed datetime or None if invalid
    """
    try:
        return datetime.fromisoformat(iso_string)
    except (ValueError, TypeError):
        return None


def is_expired(dt: datetime) -> bool:
    """
    Check if a datetime is in the past.
    
    Args:
        dt: Datetime to check
        
    Returns:
        bool: True if datetime is in the past
    """
    return to_utc(dt) < utc_now()


def time_until(dt: datetime) -> timedelta:
    """
    Calculate time remaining until a datetime.
    
    Args:
        dt: Target datetime
        
    Returns:
        timedelta: Time remaining (negative if in the past)
    """
    return to_utc(dt) - utc_now()


def time_since(dt: datetime) -> timedelta:
    """
    Calculate time elapsed since a datetime.
    
    Args:
        dt: Past datetime
        
    Returns:
        timedelta: Time elapsed (negative if in the future)
    """
    return utc_now() - to_utc(dt)