import re

BAD_WORDS = {
    "хуй", "пизд", "ебать", "блядь", "сука", "гандон", "дроч", "мудак",
    "шлюха", "шалава", "проститутка", "залупа", "жопа", "член", "петух",
    "нац", "нацист", "холокост", "порно", "секс", "трахать"
}

OBFUSCATION_PATTERNS = [
    r"[хxXхХ][уyYуУ][йiIйЙ]",
    r"[пpP][иiI][з3Z][дdD]",
    r"[eеE][бbB][aаA][тtT]",
    r"[cсС][уyY][кkK][aаA]",
]

def contains_profanity(text: str) -> bool:
    text_lower = text.lower()
    
    for word in BAD_WORDS:
        if word in text_lower:
            return True
    
    for pattern in OBFUSCATION_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    
    if re.search(r"https?://(?!twitch\.tv|youtube\.com)", text_lower):
        return True
    
    letters = [c for c in text if c.isalpha()]
    if letters and sum(1 for c in letters if c.isupper()) / len(letters) > 0.7:
        return True
    
    return False

def sanitize_text(text: str, max_length: int = 150) -> str:
    text = re.sub(r"https?://(?!twitch\.tv|youtube\.com)[^\s]+", "[ссылка удалена]", text)
    
    text = re.sub(
        r"[^\w\sа-яА-ЯёЁa-zA-Z0-9.,!?;:\-\'\"()]+",
        " ",
        text,
        flags=re.UNICODE
    )
    
    text = " ".join(text.split())
    text = text[:max_length].strip()
    
    if text and not text.endswith((".", "!", "?", "…")):
        text += "."
    
    return text