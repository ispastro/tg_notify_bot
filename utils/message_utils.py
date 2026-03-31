"""Message personalization utilities."""


def personalize_message(message: str, full_name: str) -> str:
    """
    Prepend 'ሰላም [Name]' greeting to message.
    
    Args:
        message: The broadcast message
        full_name: User's registered full name
        
    Returns:
        Personalized message with greeting prepended
    """
    if not full_name:
        return message
    return f"ሰላም {full_name}\n{message}"
