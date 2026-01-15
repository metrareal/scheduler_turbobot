# 📅 Planner Bot <p align="center"> <img src="https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python"> <img src="https://img.shields.io/badge/Telegram-Bot-26A5E4?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram"> <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License"> </p>
## 📋 Возможности

- ✅ Создание задач
- 📝 Просмотр списка дел
- 🗑️ Удаление выполненных задач
- 💾 Сохранение данных в JSON

## 🚀 Установка

### 1. Клонируйте репозиторий

```bash
git clone https://github.com/your-username/planner-bot.git
cd planner-bot
````

### 2. Создайте виртуальное окружение

```bash
python -m venv venv
```

*Активация*:

- Windows:
```bash
venv\Scripts\activate
```
- Linux/Mac:
```bash
source venv/bin/activate
```

### 3. Установите зависимости

```bash
pip install -r requirements.txt
```

### 4. Настройте переменные окружения

Создайте файл `.env` в корне проекта:
```bash
BOT_TOKEN=your_telegram_bot_token
```
💡 *Получить токен можно у [@BotFather](https://t.me/BotFather)*

### 5. Запустите бота

```bash
python bot.py
```

### 📁 Структура проекта

```text
planner-bot/
├── bot.py                # Главный файл бота
├── requirements.txt      # Зависимости
├── .env.example          # Файл для токена бота
├── .gitignore            # Игнорируемые файлы
└── README.md             # Документация
```

### 🛠️ Технологии

- [Python 3.10+](https://www.python.org/)
- [python-telegram-bot](https://python-telegram-bot.org/) / [aiogram](https://aiogram.dev/)
- JSON для хранения данных

### 📄 Лицензия

Этот проект распространяется под лицензией MIT. См. файл [LICENSE](https://lmarena.ai/c/LICENSE) для подробностей.

### 📞 Контакты

- Telegram: [*тык*](https://t.me/speciallyforsomeone)
- GitHub: [*тык*](https://github.com/metrareal)