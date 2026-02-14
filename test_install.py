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
