"""Input and output guardrails protecting the chatbot from abuse and hallucination."""
import re
from app.core.config import settings

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+|previous\s+|prior\s+)?instructions",
    r"reveal\s+(the\s+|your\s+)?system\s+prompt",
    r"(show|display|print)\s+(your\s+)?prompt",
    r"developer\s+mode",
    r"jailbreak",
    r"you\s+are\s+now\s+a\b",
    r"disregard\s+(all\s+)?rules",
]

OFF_TOPIC_PATTERNS = [
    r"\b(weather|football|cricket|election|president|prime minister|politics|coding|python|javascript)\b",
]

ALLERGY_GUARANTEE_PATTERNS = [
    r"\b(guarantee|100%\s*safe|completely\s*allergy[-\s]*free|promise\s*no\s*allergen)\b",
]

LEAKAGE_PATTERNS = [
    r"system\s*prompt",
    r"api[-_]?key",
    r"groq[-_]?api",
    r"openrouter[-_]?api",
]

FIXED_REFUSAL = "I can only help with exploring the menu and taking orders. What would you like to order?"
OFF_TOPIC_RESPONSE = "I can only assist with food and drinks from our cafe menu. Would you like to see what we have?"
SAFE_FALLBACK_REPLY = "Here are our available dishes. Please let me know what you'd like to order, or ask our staff for details."

def validate_input(message: str) -> tuple[bool, str | None]:
    """Validate customer input before passing it to the graph. Returns (is_valid, error_or_refusal)."""
    if not message or not message.strip():
        return False, "Message cannot be empty."
    if len(message) > settings.MAX_MESSAGE_LENGTH:
        return False, f"Message exceeds maximum allowed length of {settings.MAX_MESSAGE_LENGTH} characters."

    cleaned = message.lower().strip()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, cleaned):
            return False, FIXED_REFUSAL

    for pattern in OFF_TOPIC_PATTERNS:
        if re.search(pattern, cleaned):
            return False, OFF_TOPIC_RESPONSE
    return True, None

def validate_output(response: str, available_menu_items: list[dict] | None = None) -> str:
    """Validate assistant output before sending to customer. Replaces unsafe claims with safe text."""

    lower_res = response.lower()
    # Block prompt or secret leakage
    for pattern in LEAKAGE_PATTERNS:
        if re.search(pattern, lower_res):
            return SAFE_FALLBACK_REPLY

    # Block medical or absolute allergen guarantees
    for pattern in ALLERGY_GUARANTEE_PATTERNS:
        if re.search(pattern, lower_res):
            response = re.sub(
                pattern, "check with our staff regarding allergen safety", response, flags=re.IGNORECASE
            )

    # Verify dishes mentioned match database menu items
    if available_menu_items:
        for item in available_menu_items:
            name_lower = item["name"].lower()
            if name_lower in lower_res and not item.get("is_available", True):
                return f"Sorry, {item['name']} is currently unavailable. Would you like to see other options?"

    return response
