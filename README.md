# Agents-Development
Работа подготовлена студентом 522 группы Канта Даниэлем. (В рамках спецкурса "Разработка агентов ИИ" на ВМК)

Задание посвящено разработке системы, позволяющей анализировать сообщения в выбранных чатах Телеграм за выбранный период и формирование саммари по результатам. Кроме того реализация диалоговой системы, для ответа на вопросы.
Структура:
├── app/
├── logs/
├── data/
├── scripts/
├── .env
├── docker-compose.yml
├── requirements.txt
└── README.md

# Часть 0. Подготовка
Python version 3.12.3

```
docker compose up -d
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
Не забудьте в .env изменить данные (я использовал ключ HF_HUB)

# Часть 1. Login
```
python3 -m scripts.telegram_login
```

# Часть 2. Запуск
```
python3 -m scripts.run_ui
```
