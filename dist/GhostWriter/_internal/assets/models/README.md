# Локальные веса faster-whisper (режим `stt_local.model_source: "bundle"`)

1. Скачайте модель (пример для `small`):

   ```bash
   huggingface-cli download systran/faster-whisper-small --local-dir ./small
   ```

2. Положите каталог с весами сюда: `assets/models/small/` (имя папки должно совпадать с `local_whisper_model` в `config.json`).

3. В `config.json` укажите:

   ```json
   "local_whisper_model": "small",
   "stt_local": { "model_source": "bundle", "device": "cpu", "compute_type": "int8" }
   ```

4. Пересоберите `.app`: при наличии этой папки `GhostWriter.spec` добавит её в `datas` как `assets/models`.

Пустой репозиторий без моделей собирается как «тонкий» клиент с `model_source: "cache"` (скачивание в кэш HF при первом использовании).
