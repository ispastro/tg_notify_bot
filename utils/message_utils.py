"""Message personalization utilities."""


def personalize_message(message: str, full_name: str) -> str:
    """
    Replace {name} placeholder with user's full name.
    
    Args:
        message: Template message with {name} placeholder
        full_name: User's registered full name
        
    Returns:
        Personalized message with name inserted
    """
    if not full_name:
        return message
    return message.replace("{name}", full_name)
