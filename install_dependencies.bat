@echo off
:: Батник для установки зависимостей TTS бота
:: Автор: TTS_PIPE
:: Версия: 1.0

echo.
echo === Установка зависимостей TTS бота ===
echo.

:: Проверка наличия Python
echo Проверка наличия Python...
python --version
if %errorlevel% neq 0 (
    echo.
    echo ОШИБКА: Python не найден. Установите Python 3.8 или выше.
    echo Скачать можно с https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

:: Проверка наличия pip
echo Проверка наличия pip...
pip --version
if %errorlevel% neq 0 (
    echo.
    echo ОШИБКА: pip не найден. Установите pip вместе с Python.
    echo.
    pause
    exit /b 1
)

:: Обновление pip
echo Обновление pip...
python -m pip install --upgrade pip
if %errorlevel% neq 0 (
    echo.
    echo ВНИМАНИЕ: Не удалось обновить pip
    echo.
)

:: Установка основных библиотек
echo Установка основных библиотек...
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
if %errorlevel% neq 0 (
    echo.
    echo ВНИМАНИЕ: Не удалось установить PyTorch с CUDA. Попробуем CPU версию...
    pip install torch torchvision torchaudio
    if %errorlevel% neq 0 (
        echo.
        echo ОШИБКА: Не удалось установить PyTorch
        echo.
        pause
        exit /b 1
    )
)

pip install coqui-tts
if %errorlevel% neq 0 (
    echo.
    echo ОШИБКА: Не удалось установить Coqui TTS
    echo.
    pause
    exit /b 1
)

pip install twitchio
if %errorlevel% neq 0 (
    echo.
    echo ОШИБКА: Не удалось установить twitchio
    echo.
    pause
    exit /b 1
)

pip install sounddevice soundfile numpy psutil python-dotenv
if %errorlevel% neq 0 (
    echo.
    echo ОШИБКА: Не удалось установить дополнительные библиотеки
    echo.
    pause
    exit /b 1
)

:: Установка дополнительных библиотек для Windows
echo Установка дополнительных библиотек для Windows...
pip install pywin32
if %errorlevel% neq 0 (
    echo.
    echo ВНИМАНИЕ: Не удалось установить pywin32
    echo.
)

:: Проверка установки
echo.
echo Проверка установленных библиотек...
python -c "import torch; import TTS; import twitchio; import sounddevice; import soundfile; import numpy; import psutil; import dotenv; print('Все библиотеки установлены успешно!')"
if %errorlevel% neq 0 (
    echo.
    echo ОШИБКА: Не удалось проверить установку библиотек
    echo.
    pause
    exit /b 1
)

echo.
echo === Установка завершена успешно! ===
echo.
echo Чтобы использовать бота:
echo 1. Создайте .env файл на основе .env.example
echo 2. Укажите свои Twitch данные
echo 3. Запустите бота командой: python main.py
echo.
pause