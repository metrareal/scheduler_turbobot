import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

load_dotenv()

# Инициализация бота
bot = Bot(token=os.getenv('BOT_TOKEN'))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# Путь к базе данных
DB_PATH = Path('planner_db.json')


# FSM состояния
class TaskStates(StatesGroup):
    waiting_task = State()
    waiting_task_category = State()
    waiting_edit_title = State()
    waiting_edit_category = State()
    waiting_time = State()
    waiting_note = State()
    waiting_new_category = State()


# Класс для работы с базой данных
class Database:
    def __init__(self, path: Path):
        self.path = path
        self.data = self._load()

    def _load(self) -> Dict:
        if self.path.exists():
            with open(self.path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _save(self):
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def get_user(self, user_id: int) -> Dict:
        user_id_str = str(user_id)
        if user_id_str not in self.data:
            self.data[user_id_str] = {
                'tasks': [],
                'notes': [],
                'categories': ['Работа', 'Личное', 'Учёба', 'Здоровье', 'Покупки'],
                'settings': {
                    'notifications': True,
                    'timezone': 0
                }
            }
            self._save()
        return self.data[user_id_str]

    def save(self):
        self._save()


db = Database(DB_PATH)


# Вспомогательные функции
def get_main_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="➕ Добавить задачу", callback_data="add_task")],
        [InlineKeyboardButton(text="📋 Мои задачи", callback_data="view_tasks")],
        [InlineKeyboardButton(text="📝 Заметки", callback_data="notes_menu")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="statistics")],
        [InlineKeyboardButton(text="🗂 Категории", callback_data="categories")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
    ])


def get_tasks_keyboard(user_id: int) -> InlineKeyboardMarkup:
    user = db.get_user(user_id)
    buttons = []
    
    today_tasks = [t for t in user['tasks'] if not t.get('completed', False)]
    
    for idx, task in enumerate(today_tasks[:10]):
        status = "🔴"  # Красный кружок для активных задач
        time_str = f"{task['time']} - " if task.get('time') else ""
        buttons.append([InlineKeyboardButton(
            text=f"{status} {time_str}{task['title'][:30]}",
            callback_data=f"task_{idx}"
        )])
    
    buttons.append([
        InlineKeyboardButton(text="🗑 Очистить выполненные", callback_data="clear_completed")
    ])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_task_detail_keyboard(task_idx: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="✅ Выполнить", callback_data=f"complete_{task_idx}")],
        [InlineKeyboardButton(text="✏️ Изменить", callback_data=f"edit_{task_idx}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_{task_idx}")],
        [InlineKeyboardButton(text="◀️ К задачам", callback_data="view_tasks")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_edit_keyboard(task_idx: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="📝 Изменить название", callback_data=f"edit_title_{task_idx}")],
        [InlineKeyboardButton(text="🏷 Изменить категорию", callback_data=f"edit_cat_{task_idx}")],
        [InlineKeyboardButton(text="◀️ Назад к задаче", callback_data=f"task_{task_idx}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_category_selection_keyboard(user_id: int, action_prefix: str) -> InlineKeyboardMarkup:
    user = db.get_user(user_id)
    buttons = []
    
    # Кнопка "Без категории"
    buttons.append([InlineKeyboardButton(text="❌ Без категории", callback_data=f"{action_prefix}_Без категории")])
    
    # Все категории пользователя
    for cat in user['categories']:
        buttons.append([InlineKeyboardButton(text=f"🏷 {cat}", callback_data=f"{action_prefix}_{cat}")])
    
    buttons.append([InlineKeyboardButton(text="◀️ Отмена", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_categories_keyboard(user_id: int) -> InlineKeyboardMarkup:
    user = db.get_user(user_id)
    buttons = []
    
    for cat in user['categories']:
        count = sum(1 for t in user['tasks'] if t.get('category') == cat and not t.get('completed'))
        buttons.append([
            InlineKeyboardButton(text=f"{cat} ({count})", callback_data=f"filter_{cat}"),
            InlineKeyboardButton(text="🗑", callback_data=f"delcat_{cat}")
        ])
    
    buttons.append([InlineKeyboardButton(text="➕ Добавить категорию", callback_data="add_category")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_notes_keyboard(user_id: int) -> InlineKeyboardMarkup:
    user = db.get_user(user_id)
    buttons = []
    
    for idx, note in enumerate(user['notes'][:10]):
        preview = note['text'][:40] + "..." if len(note['text']) > 40 else note['text']
        buttons.append([InlineKeyboardButton(
            text=f"📄 {preview}",
            callback_data=f"note_{idx}"
        )])
    
    buttons.append([InlineKeyboardButton(text="➕ Добавить заметку", callback_data="add_note")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_note_detail_keyboard(note_idx: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🗑 Удалить заметку", callback_data=f"delnote_{note_idx}")],
        [InlineKeyboardButton(text="◀️ К заметкам", callback_data="notes_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_timezone_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    timezones = [
        ("UTC-12", -12), ("UTC-11", -11), ("UTC-10", -10),
        ("UTC-9", -9), ("UTC-8", -8), ("UTC-7", -7),
        ("UTC-6", -6), ("UTC-5", -5), ("UTC-4", -4),
        ("UTC-3", -3), ("UTC-2", -2), ("UTC-1", -1),
        ("UTC+0", 0), ("UTC+1", 1), ("UTC+2", 2),
        ("UTC+3 (МСК)", 3), ("UTC+4", 4), ("UTC+5", 5),
        ("UTC+6", 6), ("UTC+7", 7), ("UTC+8", 8),
        ("UTC+9", 9), ("UTC+10", 10), ("UTC+11", 11), ("UTC+12", 12)
    ]
    
    row = []
    for label, tz in timezones:
        row.append(InlineKeyboardButton(text=label, callback_data=f"tz_{tz}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    
    if row:
        buttons.append(row)
    
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="settings")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def format_tasks_list(tasks: List[Dict], title: str = "Ваши задачи") -> str:
    if not tasks:
        return f"📋 {title}\n\nЗадач пока нет."
    
    text = f"📋 {title}\n\n"
    active_tasks = [t for t in tasks if not t.get('completed')]
    
    for task in active_tasks:
        time_str = f"⏰ {task['time']} | " if task.get('time') else ""
        cat_str = f"🏷 {task['category']} | " if task.get('category') else ""
        created = datetime.fromisoformat(task['created']).strftime('%d.%m')
        
        text += f"▪️ {task['title']}\n"
        text += f"   {time_str}{cat_str}создано: {created}\n\n"
    
    completed_tasks = [t for t in tasks if t.get('completed')]
    if completed_tasks:
        text += f"\n✅ Выполнено: {len(completed_tasks)}"
    
    return text


def get_statistics(user_id: int) -> str:
    user = db.get_user(user_id)
    tasks = user['tasks']
    
    total = len(tasks)
    completed = sum(1 for t in tasks if t.get('completed'))
    active = total - completed
    
    today = datetime.now().date()
    today_tasks = [t for t in tasks 
                   if datetime.fromisoformat(t['created']).date() == today]
    today_completed = sum(1 for t in today_tasks if t.get('completed'))
    
    categories_stats = {}
    for task in tasks:
        cat = task.get('category', 'Без категории')
        if cat not in categories_stats:
            categories_stats[cat] = {'total': 0, 'completed': 0}
        categories_stats[cat]['total'] += 1
        if task.get('completed'):
            categories_stats[cat]['completed'] += 1
    
    text = "📊 **Статистика**\n\n"
    text += f"📌 Всего задач: {total}\n"
    text += f"✅ Выполнено: {completed}\n"
    text += f"🔴 Активных: {active}\n\n"
    
    if total > 0:
        completion_rate = (completed / total) * 100
        text += f"📈 Процент выполнения: {completion_rate:.1f}%\n\n"
    
    text += f"📅 Сегодня:\n"
    text += f"   Создано: {len(today_tasks)}\n"
    text += f"   Выполнено: {today_completed}\n\n"
    
    if categories_stats:
        text += "📊 По категориям:\n"
        for cat, stats in categories_stats.items():
            text += f"   • {cat}: {stats['completed']}/{stats['total']}\n"
    
    return text


# Обработчики команд
@router.message(Command("start"))
async def cmd_start(message: Message):
    user = db.get_user(message.from_user.id)
    
    welcome_text = (
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        "Я помогу тебе организовать твой день.\n"
        "Выбери действие из меню ниже:"
    )
    
    await message.answer(welcome_text, reply_markup=get_main_keyboard())


@router.callback_query(F.data == "main_menu")
async def show_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text = "🏠 Главное меню\n\nВыбери действие:"
    await callback.message.edit_text(text, reply_markup=get_main_keyboard())


@router.callback_query(F.data == "add_task")
async def add_task_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📝 Введите название задачи:",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(TaskStates.waiting_task)


@router.message(TaskStates.waiting_task)
async def add_task_select_category(message: Message, state: FSMContext):
    await state.update_data(task_title=message.text)
    
    sent_msg = await message.answer(
        "🏷 Выберите категорию для задачи:",
        reply_markup=get_category_selection_keyboard(message.from_user.id, "newcat")
    )
    await state.update_data(last_message_id=sent_msg.message_id)
    await state.set_state(TaskStates.waiting_task_category)


@router.callback_query(F.data.startswith("newcat_"), StateFilter(TaskStates.waiting_task_category))
async def add_task_finish(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split("_", 1)[1]
    if category == "Без категории":
        category = None
    
    data = await state.get_data()
    task_title = data.get('task_title')
    
    user = db.get_user(callback.from_user.id)
    
    new_task = {
        'title': task_title,
        'created': datetime.now().isoformat(),
        'completed': False,
        'time': None,
        'category': category
    }
    
    user['tasks'].append(new_task)
    db.save()
    
    cat_text = f" (🏷 {category})" if category else ""
    await callback.message.edit_text(
        f"✅ Задача добавлена!\n\n{task_title}{cat_text}",
        reply_markup=get_main_keyboard()
    )
    await state.clear()


@router.callback_query(F.data == "view_tasks")
async def view_tasks(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    text = format_tasks_list(user['tasks'])
    
    await callback.message.edit_text(text, reply_markup=get_tasks_keyboard(callback.from_user.id))


@router.callback_query(F.data.startswith("task_"))
async def task_detail(callback: CallbackQuery):
    task_idx = int(callback.data.split("_")[1])
    user = db.get_user(callback.from_user.id)
    
    active_tasks = [t for t in user['tasks'] if not t.get('completed')]
    
    if task_idx >= len(active_tasks):
        await callback.answer("Задача не найдена")
        return
    
    task = active_tasks[task_idx]
    
    text = f"📌 **{task['title']}**\n\n"
    text += f"⏰ Время: {task.get('time', 'не указано')}\n"
    text += f"🏷 Категория: {task.get('category', 'не указана')}\n"
    text += f"📅 Создано: {datetime.fromisoformat(task['created']).strftime('%d.%m.%Y %H:%M')}\n"
    
    await callback.message.edit_text(text, reply_markup=get_task_detail_keyboard(task_idx))


@router.callback_query(F.data.regexp(r'^edit_\d+$'))


@router.callback_query(F.data.startswith("edit_title_"))
async def edit_task_title_start(callback: CallbackQuery, state: FSMContext):
    task_idx = int(callback.data.split("_")[2])
    
    await state.update_data(edit_task_idx=task_idx)
    await callback.message.edit_text(
        "📝 Введите новое название задачи:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data=f"task_{task_idx}")]
        ])
    )
    await state.set_state(TaskStates.waiting_edit_title)


@router.message(TaskStates.waiting_edit_title)
async def edit_task_title_finish(message: Message, state: FSMContext):
    data = await state.get_data()
    task_idx = data.get('edit_task_idx')
    
    user = db.get_user(message.from_user.id)
    active_tasks = [i for i, t in enumerate(user['tasks']) if not t.get('completed')]
    
    if task_idx < len(active_tasks):
        real_idx = active_tasks[task_idx]
        user['tasks'][real_idx]['title'] = message.text
        db.save()
        
        await message.answer(
            f"✅ Название изменено!\n\n{message.text}",
            reply_markup=get_edit_keyboard(task_idx)
        )
    
    await state.clear()


@router.callback_query(F.data.startswith("edit_cat_"))
async def edit_task_category_start(callback: CallbackQuery, state: FSMContext):
    task_idx = int(callback.data.split("_")[2])
    
    await state.update_data(edit_task_idx=task_idx)
    await callback.message.edit_text(
        "🏷 Выберите новую категорию:",
        reply_markup=get_category_selection_keyboard(callback.from_user.id, "editcat")
    )
    await state.set_state(TaskStates.waiting_edit_category)


@router.callback_query(F.data.startswith("editcat_"), StateFilter(TaskStates.waiting_edit_category))
async def edit_task_category_finish(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split("_", 1)[1]
    if category == "Без категории":
        category = None
    
    data = await state.get_data()
    task_idx = data.get('edit_task_idx')
    
    user = db.get_user(callback.from_user.id)
    active_tasks = [i for i, t in enumerate(user['tasks']) if not t.get('completed')]
    
    if task_idx < len(active_tasks):
        real_idx = active_tasks[task_idx]
        user['tasks'][real_idx]['category'] = category
        db.save()
        
        cat_text = category if category else "Без категории"
        await callback.message.edit_text(
            f"✅ Категория изменена на: {cat_text}",
            reply_markup=get_edit_keyboard(task_idx)
        )
    
    await state.clear()


@router.callback_query(F.data.startswith("complete_"))
async def complete_task(callback: CallbackQuery):
    task_idx = int(callback.data.split("_")[1])
    user = db.get_user(callback.from_user.id)
    
    active_tasks = [i for i, t in enumerate(user['tasks']) if not t.get('completed')]
    
    if task_idx < len(active_tasks):
        real_idx = active_tasks[task_idx]
        user['tasks'][real_idx]['completed'] = True
        user['tasks'][real_idx]['completed_at'] = datetime.now().isoformat()
        db.save()
        
        await callback.answer("✅ Задача выполнена!")
        await view_tasks(callback)


@router.callback_query(F.data.startswith("delete_"))
async def delete_task(callback: CallbackQuery):
    task_idx = int(callback.data.split("_")[1])
    user = db.get_user(callback.from_user.id)
    
    active_tasks = [i for i, t in enumerate(user['tasks']) if not t.get('completed')]
    
    if task_idx < len(active_tasks):
        real_idx = active_tasks[task_idx]
        task_title = user['tasks'][real_idx]['title']
        del user['tasks'][real_idx]
        db.save()
        
        await callback.answer(f"🗑 Удалено: {task_title}")
        await view_tasks(callback)


@router.callback_query(F.data == "clear_completed")
async def clear_completed(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    completed_count = sum(1 for t in user['tasks'] if t.get('completed'))
    
    user['tasks'] = [t for t in user['tasks'] if not t.get('completed')]
    db.save()
    
    await callback.answer(f"🗑 Удалено {completed_count} выполненных задач")
    await view_tasks(callback)


@router.callback_query(F.data == "statistics")
async def show_statistics(callback: CallbackQuery):
    text = get_statistics(callback.from_user.id)
    await callback.message.edit_text(text, reply_markup=get_back_keyboard())


@router.callback_query(F.data == "categories")
async def show_categories(callback: CallbackQuery):
    text = "🗂 **Категории задач**\n\nУправляйте категориями:"
    await callback.message.edit_text(
        text,
        reply_markup=get_categories_keyboard(callback.from_user.id)
    )


@router.callback_query(F.data.startswith("filter_"))
async def filter_by_category(callback: CallbackQuery):
    category = callback.data.split("_", 1)[1]
    user = db.get_user(callback.from_user.id)
    
    filtered_tasks = [t for t in user['tasks'] if t.get('category') == category]
    text = format_tasks_list(filtered_tasks, f"Категория: {category}")
    
    await callback.message.edit_text(text, reply_markup=get_back_keyboard())


@router.callback_query(F.data == "add_category")
async def add_category_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🏷 Введите название новой категории:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="categories")]
        ])
    )
    await state.set_state(TaskStates.waiting_new_category)


@router.message(TaskStates.waiting_new_category)
async def add_category_finish(message: Message, state: FSMContext):
    user = db.get_user(message.from_user.id)
    
    new_category = message.text.strip()
    
    if new_category not in user['categories']:
        user['categories'].append(new_category)
        db.save()
        
        await message.answer(
            f"✅ Категория '{new_category}' добавлена!",
            reply_markup=get_categories_keyboard(message.from_user.id)
        )
    else:
        await message.answer(
            "❌ Такая категория уже существует!",
            reply_markup=get_categories_keyboard(message.from_user.id)
        )
    
    await state.clear()


@router.callback_query(F.data.startswith("delcat_"))
async def delete_category(callback: CallbackQuery):
    category = callback.data.split("_", 1)[1]
    user = db.get_user(callback.from_user.id)
    
    if category in user['categories']:
        user['categories'].remove(category)
        
        # Убираем категорию у всех задач с этой категорией
        for task in user['tasks']:
            if task.get('category') == category:
                task['category'] = None
        
        db.save()
        await callback.answer(f"🗑 Категория '{category}' удалена")
        await show_categories(callback)


@router.callback_query(F.data == "notes_menu")
async def notes_menu(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    
    text = "📝 **Заметки**\n\n"
    
    if user['notes']:
        text += "Нажмите на заметку, чтобы открыть её полностью:"
    else:
        text += "Заметок пока нет."
    
    await callback.message.edit_text(text, reply_markup=get_notes_keyboard(callback.from_user.id))


@router.callback_query(F.data.startswith("note_"))
async def show_note_detail(callback: CallbackQuery):
    note_idx = int(callback.data.split("_")[1])
    user = db.get_user(callback.from_user.id)
    
    if note_idx >= len(user['notes']):
        await callback.answer("Заметка не найдена")
        return
    
    note = user['notes'][note_idx]
    created = datetime.fromisoformat(note['created']).strftime('%d.%m.%Y %H:%M')
    
    text = f"📄 **Заметка**\n\n{note['text']}\n\n📅 Создано: {created}"
    
    await callback.message.edit_text(text, reply_markup=get_note_detail_keyboard(note_idx))


@router.callback_query(F.data == "add_note")
async def add_note_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📝 Введите текст заметки:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="notes_menu")]
        ])
    )
    await state.set_state(TaskStates.waiting_note)


@router.message(TaskStates.waiting_note)
async def add_note_finish(message: Message, state: FSMContext):
    user = db.get_user(message.from_user.id)
    
    new_note = {
        'text': message.text,
        'created': datetime.now().isoformat()
    }
    
    user['notes'].append(new_note)
    db.save()
    
    await message.answer(
        "✅ Заметка сохранена!",
        reply_markup=get_notes_keyboard(message.from_user.id)
    )
    await state.clear()


@router.callback_query(F.data.startswith("delnote_"))
async def delete_note(callback: CallbackQuery):
    note_idx = int(callback.data.split("_")[1])
    user = db.get_user(callback.from_user.id)
    
    if note_idx < len(user['notes']):
        del user['notes'][note_idx]
        db.save()
        
        await callback.answer("🗑 Заметка удалена")
        await notes_menu(callback)


@router.callback_query(F.data == "settings")
async def show_settings(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    settings = user['settings']
    
    text = "⚙️ **Настройки**\n\n"
    text += f"🔔 Уведомления: {'Вкл' if settings['notifications'] else 'Выкл'}\n"
    text += f"🌍 Часовой пояс: UTC{settings['timezone']:+d}\n"
    
    buttons = [
        [InlineKeyboardButton(
            text=f"🔔 {'Выключить' if settings['notifications'] else 'Включить'} уведомления",
            callback_data="toggle_notifications"
        )],
        [InlineKeyboardButton(text="🌍 Изменить часовой пояс", callback_data="change_timezone")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
    ]
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query(F.data == "toggle_notifications")
async def toggle_notifications(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    user['settings']['notifications'] = not user['settings']['notifications']
    db.save()
    
    await show_settings(callback)
    
@router.callback_query(F.data == "change_timezone")
async def change_timezone_menu(callback: CallbackQuery):
    text = "🌍 **Выбор часового пояса**\n\nВыберите ваш часовой пояс:"
    await callback.message.edit_text(text, reply_markup=get_timezone_keyboard())


@router.callback_query(F.data.startswith("tz_"))
async def set_timezone(callback: CallbackQuery):
    tz = int(callback.data.split("_")[1])
    user = db.get_user(callback.from_user.id)
    user['settings']['timezone'] = tz
    db.save()
    
    await callback.answer(f"✅ Часовой пояс установлен: UTC{tz:+d}")
    await show_settings(callback)


async def main():
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
async def edit_task_menu(callback: CallbackQuery):
    task_idx = int(callback.data.split("_")[1])
    
    text = "✏️ **Изменение задачи**\n\nВыберите, что хотите изменить:"
    await callback.message.edit_text(text, reply_markup=get_edit_keyboard(task_idx))


@router.callback_query(F.data.startswith("edit_title_"))
async def edit_task_title_start(callback: CallbackQuery, state: FSMContext):
    task_idx = int(callback.data.split("_")[2])
    
    await state.update_data(edit_task_idx=task_idx)
    await callback.message.edit_text(
        "📝 Введите новое название задачи:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data=f"task_{task_idx}")]
        ])
    )
    await state.set_state(TaskStates.waiting_edit_title)


@router.message(StateFilter(TaskStates.waiting_edit_title))
async def edit_task_title_finish(message: Message, state: FSMContext):
    data = await state.get_data()
    task_idx = data.get('edit_task_idx')
    
    user = db.get_user(message.from_user.id)
    active_tasks = [i for i, t in enumerate(user['tasks']) if not t.get('completed')]
    
    if task_idx < len(active_tasks):
        real_idx = active_tasks[task_idx]
        user['tasks'][real_idx]['title'] = message.text
        db.save()
        
        await message.answer(
            f"✅ Название изменено!\n\n{message.text}",
            reply_markup=get_edit_keyboard(task_idx)
        )
    
    await state.clear()


@router.callback_query(F.data.startswith("edit_cat_"))
async def edit_task_category_start(callback: CallbackQuery, state: FSMContext):
    task_idx = int(callback.data.split("_")[2])
    
    await state.update_data(edit_task_idx=task_idx)
    await callback.message.edit_text(
        "🏷 Выберите новую категорию:",
        reply_markup=get_category_selection_keyboard(callback.from_user.id, "editcat")
    )
    await state.set_state(TaskStates.waiting_edit_category)


@router.callback_query(StateFilter(TaskStates.waiting_edit_category), F.data.startswith("editcat_"))
async def edit_task_category_finish(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split("_", 1)[1]
    if category == "Без категории":
        category = None
    
    data = await state.get_data()
    task_idx = data.get('edit_task_idx')
    
    user = db.get_user(callback.from_user.id)
    active_tasks = [i for i, t in enumerate(user['tasks']) if not t.get('completed')]
    
    if task_idx < len(active_tasks):
        real_idx = active_tasks[task_idx]
        user['tasks'][real_idx]['category'] = category
        db.save()
        
        cat_text = category if category else "Без категории"
        await callback.message.edit_text(
            f"✅ Категория изменена на: {cat_text}",
            reply_markup=get_edit_keyboard(task_idx)
        )
    
    await state.clear()


@router.callback_query(F.data.startswith("complete_"))
async def complete_task(callback: CallbackQuery):
    task_idx = int(callback.data.split("_")[1])
    user = db.get_user(callback.from_user.id)
    
    active_tasks = [i for i, t in enumerate(user['tasks']) if not t.get('completed')]
    
    if task_idx < len(active_tasks):
        real_idx = active_tasks[task_idx]
        user['tasks'][real_idx]['completed'] = True
        user['tasks'][real_idx]['completed_at'] = datetime.now().isoformat()
        db.save()
        
        await callback.answer("✅ Задача выполнена!")
        await view_tasks(callback)


@router.callback_query(F.data.startswith("delete_"))
async def delete_task(callback: CallbackQuery):
    task_idx = int(callback.data.split("_")[1])
    user = db.get_user(callback.from_user.id)
    
    active_tasks = [i for i, t in enumerate(user['tasks']) if not t.get('completed')]
    
    if task_idx < len(active_tasks):
        real_idx = active_tasks[task_idx]
        task_title = user['tasks'][real_idx]['title']
        del user['tasks'][real_idx]
        db.save()
        
        await callback.answer(f"🗑 Удалено: {task_title}")
        await view_tasks(callback)


@router.callback_query(F.data == "clear_completed")
async def clear_completed(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    completed_count = sum(1 for t in user['tasks'] if t.get('completed'))
    
    user['tasks'] = [t for t in user['tasks'] if not t.get('completed')]
    db.save()
    
    await callback.answer(f"🗑 Удалено {completed_count} выполненных задач")
    await view_tasks(callback)


@router.callback_query(F.data == "statistics")
async def show_statistics(callback: CallbackQuery):
    text = get_statistics(callback.from_user.id)
    await callback.message.edit_text(text, reply_markup=get_back_keyboard())


@router.callback_query(F.data == "categories")
async def show_categories(callback: CallbackQuery):
    text = "🗂 **Категории задач**\n\nУправляйте категориями:"
    await callback.message.edit_text(
        text,
        reply_markup=get_categories_keyboard(callback.from_user.id)
    )


@router.callback_query(F.data.startswith("filter_"))
async def filter_by_category(callback: CallbackQuery):
    category = callback.data.split("_", 1)[1]
    user = db.get_user(callback.from_user.id)
    
    filtered_tasks = [t for t in user['tasks'] if t.get('category') == category]
    text = format_tasks_list(filtered_tasks, f"Категория: {category}")
    
    await callback.message.edit_text(text, reply_markup=get_back_keyboard())


@router.callback_query(F.data == "add_category")
async def add_category_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🏷 Введите название новой категории:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="categories")]
        ])
    )
    await state.set_state(TaskStates.waiting_new_category)


@router.message(StateFilter(TaskStates.waiting_new_category))
async def add_category_finish(message: Message, state: FSMContext):
    user = db.get_user(message.from_user.id)
    
    new_category = message.text.strip()
    
    if new_category not in user['categories']:
        user['categories'].append(new_category)
        db.save()
        
        await message.answer(
            f"✅ Категория '{new_category}' добавлена!",
            reply_markup=get_categories_keyboard(message.from_user.id)
        )
    else:
        await message.answer(
            "❌ Такая категория уже существует!",
            reply_markup=get_categories_keyboard(message.from_user.id)
        )
    
    await state.clear()


@router.callback_query(F.data.startswith("delcat_"))
async def delete_category(callback: CallbackQuery):
    category = callback.data.split("_", 1)[1]
    user = db.get_user(callback.from_user.id)
    
    if category in user['categories']:
        user['categories'].remove(category)
        
        # Убираем категорию у всех задач с этой категорией
        for task in user['tasks']:
            if task.get('category') == category:
                task['category'] = None
        
        db.save()
        await callback.answer(f"🗑 Категория '{category}' удалена")
        await show_categories(callback)


@router.callback_query(F.data == "notes_menu")
async def notes_menu(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    
    text = "📝 **Заметки**\n\n"
    
    if user['notes']:
        text += "Нажмите на заметку, чтобы открыть её полностью:"
    else:
        text += "Заметок пока нет."
    
    await callback.message.edit_text(text, reply_markup=get_notes_keyboard(callback.from_user.id))


@router.callback_query(F.data.startswith("note_"))
async def show_note_detail(callback: CallbackQuery):
    note_idx = int(callback.data.split("_")[1])
    user = db.get_user(callback.from_user.id)
    
    if note_idx >= len(user['notes']):
        await callback.answer("Заметка не найдена")
        return
    
    note = user['notes'][note_idx]
    created = datetime.fromisoformat(note['created']).strftime('%d.%m.%Y %H:%M')
    
    text = f"📄 **Заметка**\n\n{note['text']}\n\n📅 Создано: {created}"
    
    await callback.message.edit_text(text, reply_markup=get_note_detail_keyboard(note_idx))


@router.callback_query(F.data == "add_note")
async def add_note_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📝 Введите текст заметки:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="notes_menu")]
        ])
    )
    await state.set_state(TaskStates.waiting_note)


@router.message(StateFilter(TaskStates.waiting_note))
async def add_note_finish(message: Message, state: FSMContext):
    user = db.get_user(message.from_user.id)
    
    new_note = {
        'text': message.text,
        'created': datetime.now().isoformat()
    }
    
    user['notes'].append(new_note)
    db.save()
    
    await message.answer(
        "✅ Заметка сохранена!",
        reply_markup=get_notes_keyboard(message.from_user.id)
    )
    await state.clear()


@router.callback_query(F.data.startswith("delnote_"))
async def delete_note(callback: CallbackQuery):
    note_idx = int(callback.data.split("_")[1])
    user = db.get_user(callback.from_user.id)
    
    if note_idx < len(user['notes']):
        del user['notes'][note_idx]
        db.save()
        
        await callback.answer("🗑 Заметка удалена")
        await notes_menu(callback)


# @router.callback_query(F.data == "settings")
# async def show_settings(callback: CallbackQuery):
#     user = db.get_user(callback.from_user.id)
#     settings = user['settings']
    
#     text = "⚙️ **Настройки**\n\n"
#     text += f"🔔 Уведомления: {'Вкл' if settings['notifications'] else 'Выкл'}\n"
#     text += f"🌍 Часовой пояс: UTC{settings['timezone']:+d}\n"
    
#     buttons = [
#         [InlineKeyboardButton(
#             text=f"🔔 {'Выключить' if settings['notifications'] else 'Включить'} уведомления",
#             callback_data="toggle_notifications"
#         )],
#         [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
#     ]
    
#     await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


# @router.callback_query(F.data == "toggle_notifications")
# async def toggle_notifications(callback: CallbackQuery):
#     user = db.get_user(callback.from_user.id)
#     user['settings']['notifications'] = not user['settings']['notifications']
#     db.save()
    
#     await show_settings(callback)


async def main():
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())