import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Определяем корень проекта
PROJECT_ROOT = Path(__file__).parent.resolve()

class Config:
    # Twitch
    BOT_USERNAME = os.getenv("TWITCH_BOT_USERNAME", "your_bot")
    BOT_TOKEN = os.getenv("TWITCH_BOT_TOKEN", "oauth:...")
    CHANNEL = os.getenv("TWITCH_CHANNEL", "your_channel")
    REWARD_ID = os.getenv("TWITCH_REWARD_ID", "").strip()
    
    # Режимы доступа
    FREE_FOR_MODS = os.getenv("FREE_FOR_MODS", "true").lower() == "true"
    FREE_FOR_BROADCASTER = os.getenv("FREE_FOR_BROADCASTER", "true").lower() == "true"
    FREE_FOR_SUBSCRIBERS = os.getenv("FREE_FOR_SUBSCRIBERS", "false").lower() == "true"
    
    # Защита от спама
    COOLDOWN_MODS = int(os.getenv("COOLDOWN_MODS", "30"))
    COOLDOWN_SUBS = int(os.getenv("COOLDOWN_SUBS", "120"))
    COOLDOWN_VIEWERS = int(os.getenv("COOLDOWN_VIEWERS", "300"))
    GLOBAL_QUEUE_LIMIT = int(os.getenv("GLOBAL_QUEUE_LIMIT", "10"))
    MAX_TEXT_LENGTH = int(os.getenv("MAX_TEXT_LENGTH", "150"))
    
    # XTTS настройки
    CPU_THREADS = int(os.getenv("CPU_THREADS", "2"))
    REFERENCE_VOICE = os.getenv("REFERENCE_VOICE", str(PROJECT_ROOT / "reference" / "voice.wav"))
    USE_VOICE_CLONING = os.getenv("USE_VOICE_CLONING", "true").lower() == "true"
    
    # Пути
    CACHE_DIR = Path(os.getenv("CACHE_DIR", str(PROJECT_ROOT / "cache")))
    QUEUE_DIR = Path(os.getenv("QUEUE_DIR", str(PROJECT_ROOT / "audio_queue")))
    REFERENCE_DIR = Path(os.getenv("REFERENCE_DIR", str(PROJECT_ROOT / "reference")))
    
    @classmethod
    def init_dirs(cls):
        cls.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cls.QUEUE_DIR.mkdir(parents=True, exist_ok=True)
        cls.REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
        print(f"[OK] Кэш директория: {cls.CACHE_DIR}")
        print(f"[OK] Очередь директория: {cls.QUEUE_DIR}")
    
    @classmethod
    def has_reward_support(cls) -> bool:
        return bool(cls.REWARD_ID)
    
    @classmethod
    def get_reference_voice(cls) -> str | None:
        """Возвращает путь к референсному аудио или None если файл не существует"""
        if not cls.USE_VOICE_CLONING:
            return None
        
        ref_path = Path(cls.REFERENCE_VOICE)
        if ref_path.exists() and ref_path.stat().st_size > 10000:  # >10 КБ
            return str(ref_path)
        return None