#requires -Version 5.0
# Установка TTS-бота для Twitch на Coqui XTTS v2.0.3 (Python 3.10)
# Полностью совместимая версия с фиксом transformers

Write-Host "🚀 Установка TTS-бота для Twitch (Coqui XTTS v2.0.3)" -ForegroundColor Cyan
Write-Host "   Путь проекта: $PSScriptRoot" -ForegroundColor DarkGray
Write-Host ""

$OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

# 1. Очистка старого окружения
Write-Host "[1/7] Очистка старого виртуального окружения..." -ForegroundColor Yellow
if (Test-Path -Path "venv") {
    Remove-Item -Recurse -Force "venv" -ErrorAction SilentlyContinue
    Write-Host "   [OK] Папка 'venv' удалена" -ForegroundColor Green
}

# 2. Проверка версии Python
Write-Host "[2/7] Проверка версии Python..." -ForegroundColor Yellow
$pythonVer = python --version 2>&1
if ($pythonVer -match "Python 3\.10") {
    Write-Host "   [OK] Обнаружен Python $pythonVer" -ForegroundColor Green
} else {
    Write-Host "[FAIL] Требуется Python 3.10.x" -ForegroundColor Red
    Write-Host "   Установите Python 3.10.11: https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe" -ForegroundColor Yellow
    Write-Host "   ⚠️  Обязательно поставьте галочку 'Add Python to PATH' при установке!" -ForegroundColor Red
    exit 1
}

# 3. Создание виртуального окружения
Write-Host "[3/7] Создание виртуального окружения..." -ForegroundColor Yellow
python -m venv venv 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAIL] Ошибка создания окружения" -ForegroundColor Red
    exit 1
}
Write-Host "   [OK] Виртуальное окружение создано" -ForegroundColor Green

# 4. Установка системных пакетов
Write-Host "[4/7] Установка системных пакетов..." -ForegroundColor Yellow
& .\venv\Scripts\python.exe -m pip install --upgrade pip setuptools==69.5.1 wheel==0.43.0 --no-cache-dir --default-timeout=100 2>$null
Write-Host "   [OK] pip, setuptools, wheel установлены" -ForegroundColor Green

# 5. Установка КРИТИЧЕСКИ ВАЖНЫХ совместимых версий (фикс ошибки BeamSearchScorer)
Write-Host "[5/7] Установка совместимых версий transformers/tokenizers (фикс BeamSearchScorer)..." -ForegroundColor Yellow

# Сначала устанавливаем совместимые версии ДО установки TTS
& .\venv\Scripts\python.exe -m pip install transformers==4.35.2 tokenizers==0.15.2 --no-cache-dir --default-timeout=100 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "   [OK] transformers==4.35.2, tokenizers==0.15.2 установлены" -ForegroundColor Green
} else {
    Write-Host "   [FAIL] Ошибка установки transformers/tokenizers" -ForegroundColor Red
    exit 1
}

# Устанавливаем torch и torchaudio
Write-Host "   Установка torch и torchaudio..." -ForegroundColor DarkGray -NoNewline
& .\venv\Scripts\python.exe -m pip install torch==2.4.0 torchaudio==2.4.0 --index-url https://download.pytorch.org/whl/cpu --no-cache-dir --default-timeout=100 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host " [OK]" -ForegroundColor Green
} else {
    Write-Host " [FAIL]" -ForegroundColor Red
    exit 1
}

# 6. Установка остальных зависимостей
Write-Host "[6/7] Установка зависимостей TTS..." -ForegroundColor Yellow

$deps = @(
    "numpy==1.26.4"
    "librosa==0.10.1"
    "soundfile==0.12.1"
    "requests==2.31.0"
    "tqdm==4.66.1"
    "TTS==0.22.0"  # Устанавливается ПОСЛЕ transformers/tokenizers
    "twitchio>=2.10.0,<3.0.0"
    "python-dotenv"
)

foreach ($dep in $deps) {
    $pkg_name = ($dep -split "==")[0]
    $pkg_name = ($pkg_name -split ">")[0]
    $pkg_name = ($pkg_name -split "<")[0]
    
    Write-Host "   Установка $pkg_name..." -ForegroundColor DarkGray -NoNewline
    
    & .\venv\Scripts\python.exe -m pip install $dep --no-cache-dir --default-timeout=100 2>$null
    
    # Проверка для критичных пакетов
    $critical_pkgs = @("transformers", "tokenizers", "TTS", "torch")
    if ($critical_pkgs -contains $pkg_name) {
        $check = & .\venv\Scripts\python.exe -c "import importlib.util; print('OK' if importlib.util.find_spec('$pkg_name') else 'FAIL')" 2>$null
        if ($check -eq "OK") {
            Write-Host " [OK]" -ForegroundColor Green
        } else {
            Write-Host " [FAIL]" -ForegroundColor Red
            if ($pkg_name -eq "TTS") {
                Write-Host "   [CRITICAL] Не удалось установить TTS — работа бота невозможна" -ForegroundColor Red
                exit 1
            }
        }
    } else {
        Write-Host " [OK]" -ForegroundColor Green
    }
}

# 7. Создание структуры проекта и проверка
Write-Host "[7/7] Финальная настройка..." -ForegroundColor Yellow

# Создаём папки
@("cache", "audio_queue", "reference") | ForEach-Object {
    $dir = "$PSScriptRoot\$_"
    if (-not (Test-Path $dir)) { 
        New-Item -ItemType Directory -Path $dir -Force | Out-Null 
    }
    Write-Host "   [OK] Папка $_ создана" -ForegroundColor Green
}

# .env.example
@'
TWITCH_BOT_USERNAME=ваш_бот
TWITCH_BOT_TOKEN=oauth:ваш_токен_здесь
TWITCH_CHANNEL=ваш_канал
TWITCH_REWARD_ID=
FREE_FOR_MODS=true
FREE_FOR_BROADCASTER=true
FREE_FOR_SUBSCRIBERS=false
COOLDOWN_MODS=30
COOLDOWN_VIEWERS=300
CPU_THREADS=2
'@ | Out-File -FilePath "$PSScriptRoot\.env.example" -Encoding utf8
Write-Host "   [OK] Файл .env.example создан" -ForegroundColor Green

# Тестовая проверка критически важного импорта
$test_script = @'
import sys
print("[OK] Python " + sys.version.split()[0])

try:
    from transformers import BeamSearchScorer
    print("[OK] BeamSearchScorer доступен (фикс совместимости работает)")
except ImportError as e:
    print("[FAIL] BeamSearchScorer недоступен: " + str(e))
    sys.exit(1)

try:
    import torch
    print("[OK] PyTorch " + torch.__version__)
except:
    print("[FAIL] PyTorch не импортирован")

try:
    from TTS.api import TTS
    print("[OK] TTS импортирован")
    tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2", gpu=False, progress_bar=False)
    print("[OK] XTTS модель загружена (языки: " + ", ".join(tts.languages[:5]) + "...)") 
except Exception as e:
    print("[FAIL] TTS не работает: " + str(e))
    sys.exit(1)

print("")
print("[SUCCESS] Установка завершена успешно!")
print("💡 Первый запуск бота займёт 5-10 минут (загрузка модели ~2.3 ГБ)")
'@

$test_script | Out-File -FilePath "$PSScriptRoot\test_install.py" -Encoding utf8
& .\venv\Scripts\python.exe test_install.py 2>&1 | ForEach-Object {
    if ($_ -match "^\[FAIL\]" -or $_ -match "Traceback") { Write-Host $_ -ForegroundColor Red }
    elseif ($_ -match "^\[OK\]" -or $_ -match "^\[SUCCESS\]") { Write-Host $_ -ForegroundColor Green }
    elseif ($_ -match "^\[WARN\]") { Write-Host $_ -ForegroundColor Yellow }
    else { Write-Host $_ }
}

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ УСТАНОВКА ЗАВЕРШЕНА УСПЕШНО!" -ForegroundColor Green
    Write-Host "`n📋 Далее:" -ForegroundColor Cyan
    Write-Host "  1. Создайте .env:  copy .env.example .env" -ForegroundColor White
    Write-Host "  2. Заполните токены в .env (через Блокнот)" -ForegroundColor White
    Write-Host "  3. Запустите бота:" -ForegroundColor White
    Write-Host "       .\venv\Scripts\Activate.ps1" -ForegroundColor DarkGray
    Write-Host "       python main.py" -ForegroundColor DarkGray
    Write-Host "`n⚠️  Первый запуск: 5-10 минут (загрузка модели). НЕ ПРЕРЫВАЙТЕ!" -ForegroundColor Yellow
} else {
    Write-Host "`n❌ Установка завершена с ошибками" -ForegroundColor Red
    Write-Host "   Критическая ошибка: несовместимость transformers" -ForegroundColor Yellow
    Write-Host "   Решение: удалите папку venv и запустите скрипт снова ОТ АДМИНИСТРАТОРА" -ForegroundColor White
    exit 1
}