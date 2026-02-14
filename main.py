#!/usr/bin/env python3
"""
TTS бот для Twitch на базе Coqui XTTS v2.0.3
Фокус: стабильная генерация чистой русской речи без ошибок inf/nan
"""

import asyncio
import hashlib
import os
import re
import signal
import sys
import subprocess
import shlex
import time
from pathlib import Path
from queue import Queue, Empty
from threading import Thread, Lock

import numpy as np
import psutil
import soundfile as sf
import torch
from twitchio.ext import commands

from config import Config
from filters import contains_profanity, sanitize_text

# Фикс кодировки для Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        # Для Python <3.7
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# === ГЛОБАЛЬНЫЕ НАСТРОЙКИ ДЛЯ МИНИМАЛЬНОЙ НАГРУЗКИ ===
torch.set_num_threads(Config.CPU_THREADS)
torch.set_grad_enabled(False)
os.environ["OMP_NUM_THREADS"] = str(Config.CPU_THREADS)
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["NUMBA_DISABLE_JIT"] = "0"

# Понижаем приоритет процесса (Windows)
try:
    p = psutil.Process()
    p.nice(psutil.IDLE_PRIORITY_CLASS)
except Exception as e:
    print(f"[WARN] Не удалось понизить приоритет: {e}")

# === ИНИЦИАЛИЗАЦИЯ COQUI XTTS ===
print("[INFO] Инициализация Coqui XTTS v2.0.3...")
from TTS.api import TTS

tts_engine = TTS(
    model_name="tts_models/multilingual/multi-dataset/xtts_v2"
)

print("[OK] XTTS модель загружена")
print(f"[INFO] Поддерживаемые языки: {tts_engine.languages}")
try:
    speakers_list = list(tts_engine.synthesizer.tts_model.speaker_manager.name_to_id.keys())
    print(f"[INFO] Первые 5 спикеров: {', '.join(speakers_list[:5])}")
except:
    print("[INFO] Список спикеров недоступен (нормально для некоторых версий)")

# === СИСТЕМА ЗАЩИТЫ ОТ СПАМА ===
class SpamProtector:
    def __init__(self):
        self.user_cooldown = {}
        self.global_queue = []
        self.lock = Lock()
    
    def check_user(self, username: str, is_mod: bool, is_sub: bool, is_broadcaster: bool) -> tuple[bool, str]:
        now = time.time()
        
        if is_broadcaster or (is_mod and Config.FREE_FOR_MODS):
            cooldown = Config.COOLDOWN_MODS
        elif is_sub and Config.FREE_FOR_SUBSCRIBERS:
            cooldown = Config.COOLDOWN_SUBS
        else:
            cooldown = Config.COOLDOWN_VIEWERS
        
        last_used = self.user_cooldown.get(username, 0)
        if now - last_used < cooldown:
            remaining = int(cooldown - (now - last_used))
            return False, f"⏳ Подожди ещё {remaining} секунд"
        
        with self.lock:
            self.global_queue = [ts for ts in self.global_queue if now - ts < 60]
            
            if len(self.global_queue) >= Config.GLOBAL_QUEUE_LIMIT:
                return False, f"⏸️ Очередь переполнена ({len(self.global_queue)}/{Config.GLOBAL_QUEUE_LIMIT})"
            
            self.global_queue.append(now)
            self.user_cooldown[username] = now
        
        return True, ""
    
    def reset_user(self, username: str):
        self.user_cooldown.pop(username, None)

protector = SpamProtector()

# === ОЧЕРЕДЬ ЗАДАЧ ===
task_queue: Queue = Queue(maxsize=Config.GLOBAL_QUEUE_LIMIT * 2)

# === TTS ВОРКЕР ===
import subprocess
import shlex

def text_to_speech(text: str, output_path: Path) -> bool:
    """Генерация речи через tts """
    start_time = time.time()
    
    try:
        # Проверка кэша
        cache_key = hashlib.md5(text.encode("utf-8")).hexdigest() + ".wav"
        cache_path = Config.CACHE_DIR / cache_key
        
        if cache_path.exists():
            if not output_path.exists():
                os.link(cache_path, output_path)
            print(f"[CACHE] ({time.time() - start_time:.2f}с): {text[:40]}...")
            return True
        
        # АГРЕССИВНАЯ САНИТАЦИЯ ТЕКСТА (защита от инъекций + стабильность)
        text = re.sub(r'[^а-яА-ЯёЁa-zA-Z0-9\s.,!?;:\-\'"()]', ' ', text)
        text = text.replace("…", "...").replace("—", "-").replace("«", "\"").replace("»", "\"")
        text = " ".join(text.split()).lower()
        text = text[:Config.MAX_TEXT_LENGTH].strip()
        if text and not text.endswith((".", "!", "?")):
            text += "."
        
        # Путь к консольной утилите tts (находится в venv/Scripts/tts.exe на Windows)
        tts_executable = Path(sys.executable).parent / "tts.exe"
        
        # Если tts.exe не найден — пробуем через python -m TTS.bin.synthesize
        if not tts_executable.exists():
            print(f"[WARN] tts.exe не найден в {tts_executable}, используем альтернативный вызов")
            cmd = [
                sys.executable, "-m", "TTS.bin.synthesize",
                "--model_name", "tts_models/multilingual/multi-dataset/xtts_v2",
                "--text", text,
                "--speaker_idx", "Claribel Dervla",
                "--language_idx", "ru",
                "--out_path", str(output_path)
            ]
        else:
            # Формируем команду для Windows (с правильной экранировкой)
            # ВАЖНО: на Windows НЕ используем shlex.quote — ломает кириллицу
            cmd = [
                str(tts_executable),
                "--model_name", "tts_models/multilingual/multi-dataset/xtts_v2",
                "--text", text,
                "--speaker_idx", "Claribel Dervla",
                "--language_idx", "ru",
                "--out_path", str(output_path)
            ]
        
        print(f"[TTS] Вызов консольной утилиты: tts \"...{text[:30]}...\"")
        
        # Выполняем команду с таймаутом 30 секунд
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            timeout=30
        )
        
        if result.returncode != 0:
            print(f"[ERROR] tts завершился с кодом {result.returncode}")
            print(f"stderr: {result.stderr[:200]}")
            return False
        
        # Проверяем, что файл создан
        if not output_path.exists() or output_path.stat().st_size < 1000:
            print(f"[ERROR] Файл не создан или пустой: {output_path}")
            return False
        
        # После успешной генерации (перед кэшированием):
        if output_path.exists():
            # Создаём/обновляем символическую ссылку на последний файл
            latest_path = Config.QUEUE_DIR / "latest.wav"
            if latest_path.exists() or latest_path.is_symlink():
                try:
                    latest_path.unlink()
                except:
                    pass
            try:
                os.symlink(output_path, latest_path)
            except:
                # На Windows без прав администратора создаём копию
                import shutil
                shutil.copy2(output_path, latest_path)

        # Кэширование
        if not cache_path.exists():
            os.link(output_path, cache_path)
        
        elapsed = time.time() - start_time
        print(f"[TTS] Сгенерировано ({elapsed:.2f}с): \"{text[:50]}\"")
        return True
        
    except subprocess.TimeoutExpired:
        print(f"[ERROR] Таймаут генерации (30 сек)")
        return False
    except Exception as e:
        print(f"[ERROR] Ошибка генерации: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        try:
            sf.write(str(output_path), np.zeros(24000, dtype=np.float32), 24000)
        except:
            pass
        return False

def tts_worker():
    """Фоновый воркер обработки очереди"""
    print("[WORKER] TTS воркер запущен (CPU, приоритет IDLE)")
    
    while True:
        try:
            # Ждём задачу с таймаутом
            try:
                task = task_queue.get(timeout=1.0)
            except Empty:
                continue  # Очередь пуста — продолжаем цикл
            
            # Обработка задачи
            try:
                text, output_path = task
                print(f"[WORKER] Обработка: \"{text[:50]}...\" -> {output_path.name}")
                success = text_to_speech(text, output_path)
                
                if success:
                    print(f"[WORKER] ✅ Готово: {output_path.name}")
                else:
                    print(f"[WORKER] ❌ Ошибка генерации: {output_path.name}")
            finally:
                task_queue.task_done()
                
        except KeyboardInterrupt:
            print("[WORKER] Остановлен по сигналу KeyboardInterrupt")
            break
        except Exception as e:
            import traceback
            print(f"[WORKER] КРИТИЧЕСКАЯ ОШИБКА: {type(e).__name__}: {e}")
            print(traceback.format_exc())

# === TWITCH БОТ ===
class HybridTTSBot(commands.Bot):
    def __init__(self):
        super().__init__(
            token=Config.BOT_TOKEN,
            prefix="!",
            initial_channels=[Config.CHANNEL],
            nick=Config.BOT_USERNAME,
        )
        self.queue_counter = 0
        self.last_announcement = 0
    
    async def event_ready(self):
        print(f"[OK] Бот @{self.nick} запущен в канале #{Config.CHANNEL}")
        
        if Config.has_reward_support():
            print(f"[INFO] Поддержка наград: ВКЛЮЧЕНА (ID: {Config.REWARD_ID})")
        else:
            print(f"[INFO] Поддержка наград: ОТКЛЮЧЕНА")
        
        ref_voice = Config.get_reference_voice()
        if ref_voice:
            print(f"[INFO] Референсный голос: {ref_voice}")
        else:
            print(f"[INFO] Референсный голос: НЕ НАСТРОЕН (используется встроенный спикер)")
        
        print(f"[INFO] Права доступа:")
        if Config.FREE_FOR_BROADCASTER:
            print(f"      • Стример: бесплатно, кулдаун {Config.COOLDOWN_MODS}с")
        if Config.FREE_FOR_MODS:
            print(f"      • Модераторы: бесплатно, кулдаун {Config.COOLDOWN_MODS}с")
        if Config.FREE_FOR_SUBSCRIBERS:
            print(f"      • Подписчики: кулдаун {Config.COOLDOWN_SUBS}с")
        print(f"      • Остальные: кулдаун {Config.COOLDOWN_VIEWERS}с")
        print(f"[INFO] Аудио файлы: {Config.QUEUE_DIR}")
    
    async def event_message(self, message):
        if message.echo:
            return
        
        # Обработка награды за баллы
        if Config.has_reward_support() and hasattr(message, 'tags'):
            reward_id = message.tags.get('custom-reward-id')
            if reward_id == Config.REWARD_ID:
                await self.process_tts_request(
                    username=message.author.name,
                    text=message.content,
                    is_reward=True,
                    is_mod=False,
                    is_sub=False,
                    is_broadcaster=False
                )
                return
        
        # Обработка команды !tts
        await self.handle_commands(message)
    
    @commands.command(name="tts")
    async def tts_command(self, ctx: commands.Context):
        text = ctx.message.content[5:].strip()
        if not text:
            await ctx.send("ℹ️ Использование: !tts текст для озвучки")
            return
        
        is_broadcaster = ctx.author.name.lower() == Config.CHANNEL.lower()
        is_mod = ctx.author.is_mod
        is_sub = ctx.author.is_subscriber
        
        await self.process_tts_request(
            username=ctx.author.name,
            text=text,
            is_reward=False,
            is_mod=is_mod,
            is_sub=is_sub,
            is_broadcaster=is_broadcaster
        )
    
    @commands.command(name="ttsinfo")
    async def tts_info(self, ctx: commands.Context):
        lines = ["ℹ️ Правила озвучки:"]
        
        if Config.has_reward_support():
            lines.append("💎 Через награду за баллы канала — без ограничений")
        
        if Config.FREE_FOR_BROADCASTER or Config.FREE_FOR_MODS:
            free_users = []
            if Config.FREE_FOR_BROADCASTER:
                free_users.append("стример")
            if Config.FREE_FOR_MODS:
                free_users.append("модераторы")
            lines.append(f"✅ {', '.join(free_users)} — бесплатно через !tts")
        
        if Config.FREE_FOR_SUBSCRIBERS:
            lines.append(f"🌟 Подписчики — !tts с кулдауном {Config.COOLDOWN_SUBS}с")
        
        lines.append(f"👥 Все остальные — !tts с кулдауном {Config.COOLDOWN_VIEWERS}с")
        lines.append(f"🚫 Запрещены: мат, спам, ссылки, капс")
        
        await ctx.send(" | ".join(lines))
    
    async def process_tts_request(
        self,
        username: str,
        text: str,
        is_reward: bool,
        is_mod: bool,
        is_sub: bool,
        is_broadcaster: bool
    ):
        # Санитизация текста
        clean_text = sanitize_text(text, Config.MAX_TEXT_LENGTH)
        if not clean_text or len(clean_text) < 3:
            print(f"[SKIP] Пропущено короткое/некорректное сообщение от {username}")
            return
        
        # Фильтр мата
        if contains_profanity(clean_text):
            if is_reward:
                print(f"[FILTER] Проигнорирована награда от {username} (мат/спам)")
                return
            else:
                await self._send_chat_message(f"@{username}, сообщение содержит запрещённый контент")
                return
        
        # Проверка кулдауна
        if not is_reward:
            allowed, reason = protector.check_user(username, is_mod, is_sub, is_broadcaster)
            if not allowed:
                now = time.time()
                if now - self.last_announcement > 10:
                    await self._send_chat_message(f"@{username}, {reason}")
                    self.last_announcement = now
                return
        else:
            protector.reset_user(username)
        
        # Добавление в очередь
        if task_queue.full():
            await self._send_chat_message(f"@{username}, очередь переполнена. Попробуй позже")
            return
        
        self.queue_counter += 1
        timestamp = int(time.time() * 1000)
        filename = f"{timestamp}_{self.queue_counter:04d}.wav"
        output_path = Config.QUEUE_DIR / filename
        
        task_queue.put((clean_text, output_path))
        
        # Уведомление в чат
        if not is_reward:
            status = "✅" if (is_broadcaster or (is_mod and Config.FREE_FOR_MODS) or (is_sub and Config.FREE_FOR_SUBSCRIBERS)) else "⏱️"
            await self._send_chat_message(f"{status} @{username}, сообщение в очереди")
        
        print(f"[QUEUE] [{self.queue_counter}] {'💎' if is_reward else '💬'} {username} ({'mod' if is_mod else 'sub' if is_sub else 'viewer'}): \"{clean_text[:60]}\"")
    
    async def _send_chat_message(self, message: str):
        try:
            channel = self.connected_channels[0]
            await channel.send(message[:480])
        except Exception as e:
            print(f"[WARN] Не удалось отправить сообщение в чат: {e}")
    
    async def event_command_error(self, ctx: commands.Context, error: Exception):
        """Подавление ошибок неизвестных команд"""
        if isinstance(error, commands.CommandNotFound):
            return
        print(f"[ERROR] Команда {ctx.command}: {type(error).__name__}: {error}")

# === ЗАПУСК ===
def signal_handler(sig, frame):
    print("\n[EXIT] Получен сигнал завершения...")
    sys.exit(0)

if __name__ == "__main__":
    # Инициализация
    Config.init_dirs()
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Совет по референсному голосу
    ref_dir = Config.REFERENCE_DIR
    if not list(ref_dir.glob("*.wav")):
        print(f"\n[INFO] Совет: Запишите 10-15 сек чистой речи и сохраните как {ref_dir / 'voice.wav'}")
        print("      Это создаст характерный голос бота вместо стандартного")
    
    # Запуск TTS воркера
    worker_thread = Thread(target=tts_worker, daemon=True)
    worker_thread.start()
    
    # Запуск бота
    bot = HybridTTSBot()
    try:
        bot.run()
    except KeyboardInterrupt:
        print("\n[EXIT] Бот остановлен")
    except Exception as e:
        print(f"[CRITICAL] Критическая ошибка: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)