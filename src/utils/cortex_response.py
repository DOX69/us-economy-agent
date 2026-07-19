def extract_message_content(data):
    message = data.get("message", {})
    if isinstance(message, str):
        raise RuntimeError(message)
    return message.get("content", [])
