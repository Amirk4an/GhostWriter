# Локальные веса faster-whisper (`stt_local.model_source: bundle`)

Чтобы приложение не качало модель из интернета при первом запуске, положите готовый каталог весов **CTranslate2** в дерево репозитория и включите режим **`bundle`**.

## 1. Скачать модель

Имя репозитория на Hugging Face обычно вида **`systran/faster-whisper-<размер>`** (`tiny`, `base`, `small`, `medium`, `large-v3`, …).

Пример для размера **`small`** (классический CLI):

```bash
huggingface-cli download systran/faster-whisper-small --local-dir ./small
```

Тот же сценарий через современный CLI **`hf`** (если установлен [Hugging Face Hub CLI](https://huggingface.co/docs/huggingface_hub/guides/cli)):

```bash
hf download systran/faster-whisper-small --local-dir ./small
```

## 2. Разместить в `assets/models/`

Каталог должен называться **точно так же**, как значение **`local_whisper_model`** в `config.json` (например `assets/models/small/` для `"local_whisper_model": "small"`).

## 3. Конфигурация

```json
"local_whisper_model": "small",
"stt_local": {
  "model_source": "bundle",
  "custom_model_path": "",
  "device": "cpu",
  "compute_type": "int8"
}
```

## 4. Сборка

При наличии `assets/models/` каталог добавляется в **`datas`** в [`GhostWriter.spec`](../GhostWriter.spec), чтобы веса попали в `.app` или в каталог `dist/GhostWriter/` на Windows.

## Режим без локальных файлов

Если **`model_source: cache`** (или блок `stt_local` опущен с дефолтом `cache`), модель подтягивается в кэш Hugging Face при первом использовании — репозиторий можно собирать без тяжёлых `assets/models/`.
