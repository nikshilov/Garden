# 🌹 Intimacy Mode ("Мост Близости")

> **Status**: Draft — P3 backlog  
> **Owner**: @GardenCore  
> **Last updated**: 2025-06-21

## 1. Problem

OpenAI / Claude models enforce strict content policies.  При попытке перейти к NSFW-сцене
персонаж не может выразить чувства так, как хотелось бы пользователю, что разрушает
иммерсию.

## 2. Solution Overview

Intimacy Mode — это *режим мостика*, в котором основной персонаж передаёт «поток
сознания» во вторую, менее модерируемую модель (Grok, Llama-3-70B-Instruct, Mixtral и
т.п.).  Пользователь получает плавное, непрерывное ощущение близости без цензуры,
при этом основные фильтры OpenAI продолжают защищать все остальные этапы диалога.

```
User  ←→  Character (GPT-4o)  —[trigger]→  Intimate Voice (Llama-3)  ←→  User
```

## 3. Trigger Mechanics

| Trigger type | Example | Notes |
|--------------|---------|-------|
| Explicit user cue | `/intimate` or emoji 🔥 | Пользователь вручную включает режим. |
| Emotion-based | affection > 0.8 **и** arousal > 0.5 | Персонаж сам решает включить, если сконфигурировано. |

Конфигурация хранится в `config.yaml` per character.

## 4. Technical Design

1. **Router Node**
   * Detects `intimacy_mode` flag in state → направляет запрос в `IntimateAgent`.
2. **IntimateAgent**
   * LLM backend выбирается из ENV `INTIMATE_MODEL` (по умолчанию `llama3-70b` via Groq).
   * Получает: последние _n_ сообщений, mood vector, relationship snapshot.
   * Возвращает полный NSFW-friendly ответ.
3. **Safety Fuse**
   * Если `SAFE_MODE=true`, Intimacy Mode отклоняется.
   * Логи маркируются `type:intimacy` и сохраняются отдельно.
4. **Cost Tracker**
   * Стоимость IntimateAgent учитывается отдельно (`cost_category="intimacy"`).

## 5. CLI / API

```
# Включить вручную
@garden > /intimate on

# Отключить
@garden > /intimate off
```

CLI-хедер показывает статус: `Intimacy: ON (model: llama3-70b)`.

## 6. Privacy & Consent

* Перед первым включением пользователь подтверждает: _«Мне 18+, я согласен на эксплицитный контент»._  
* Персонаж спрашивает согласие, если интимный порог достигнут автоматически.

## 7. Test Plan

* Unit: trigger parsing, flag propagation.  
* Integration: ensure fallback to main model when Safe Mode.  
* E2E: scripted conversation, must switch model and produce uncensored output.

## 8. Future Work

* **Voice** synthesis для интимного канала.  
* Пер-LLM fine-tuned safety filters вместо грубой замены модели.  
* User-configurable threshold sliders в UI.
