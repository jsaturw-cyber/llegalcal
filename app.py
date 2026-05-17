import os
import threading
from flask import Flask

# Создаём Flask приложение для health-проверок
flask_app = Flask(__name__)

@flask_app.route('/')
@flask_app.route('/health')
def health_check():
    return "Bot is running", 200

def start_flask():
    """Запускает Flask-сервер в отдельном потоке"""
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)

# Запускаем Flask в фоновом потоке
threading.Thread(target=start_flask, daemon=True).start()

# ============ ИМПОРТЫ ============
import asyncio
import sqlite3
import json
import re
import secrets
from datetime import datetime, timedelta
from typing import Optional

# Aiogram 2.x
from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# Парсинг
from curl_cffi import requests
from bs4 import BeautifulSoup

print("✅ Все импорты выполнены успешно!")

# ================================================================
# АВТОМАТИЧЕСКОЕ ОБНОВЛЕНИЕ КУК + ПАРСИНГ ПО GUID
# ================================================================

import json
import os
from datetime import datetime
from curl_cffi import requests
from bs4 import BeautifulSoup

# ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==========
cookies = {}
COOKIES_FILE = 'kad_cookies.json'

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С КУКАМИ ==========

def save_cookies(cookies_dict):
    """Сохраняет куки в файл"""
    with open(COOKIES_FILE, 'w') as f:
        json.dump(cookies_dict, f)
    print(f"✅ Куки сохранены ({len(cookies_dict)} шт.)")

def load_cookies():
    """Загружает куки из файла"""
    try:
        with open(COOKIES_FILE, 'r') as f:
            cookies_dict = json.load(f)
        print(f"✅ Куки загружены ({len(cookies_dict)} шт.)")
        return cookies_dict
    except FileNotFoundError:
        print("⚠️ Файл с куками не найден")
        return None

async def get_fresh_cookies():
    """Получает свежие куки через curl_cffi"""
    print("🔄 Получение свежих кук...")

    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        'Sec-Ch-Ua': '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36'
    }

    try:
        print("  → Запрос к kad.arbitr.ru...")
        response = requests.get(
            'https://kad.arbitr.ru',
            headers=headers,
            impersonate="chrome110",
            timeout=30,
            allow_redirects=True
        )

        print(f"  → Статус: {response.status_code}")

        cookies_dict = {}
        if response.cookies:
            for cookie in response.cookies:
                if hasattr(cookie, 'name') and hasattr(cookie, 'value'):
                    cookies_dict[cookie.name] = cookie.value

        if len(cookies_dict) < 3:
            print("  → Пробуем поисковый запрос для активации кук...")
            search_headers = {
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Content-Type': 'application/json',
                'Origin': 'https://kad.arbitr.ru',
                'Referer': 'https://kad.arbitr.ru/',
                'X-Requested-With': 'XMLHttpRequest',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            search_payload = {
                "Page": 1,
                "Count": 1,
                "Courts": [],
                "DateFrom": "",
                "DateTo": "",
                "CaseNumbers": ["А40-12345/2023"],
                "Judges": [],
                "Sides": [],
                "WithVKSInstances": False
            }

            search_response = requests.post(
                'https://kad.arbitr.ru/Kad/SearchInstances',
                headers=search_headers,
                json=search_payload,
                impersonate="chrome110",
                timeout=30
            )

            if search_response.cookies:
                for cookie in search_response.cookies:
                    if hasattr(cookie, 'name') and hasattr(cookie, 'value') and cookie.name not in cookies_dict:
                        cookies_dict[cookie.name] = cookie.value

        print(f"✅ Получено {len(cookies_dict)} кук")

        if len(cookies_dict) > 0:
            save_cookies(cookies_dict)
        else:
            print("⚠️ Куки не получены, создаём минимальные")
            cookies_dict = {
                'accepted_terms': 'true',
                'session_started': str(datetime.now().timestamp())
            }
            save_cookies(cookies_dict)

        return cookies_dict

    except Exception as e:
        print(f"❌ Ошибка получения кук: {e}")
        return None

async def init_cookies(force_refresh=False):
    """Инициализация кук при запуске бота"""
    global cookies

    if force_refresh:
        print("🔄 Принудительное обновление кук...")
        cookies = await get_fresh_cookies()
    else:
        cookies = load_cookies()
        if not cookies or len(cookies) < 3:
            print("⚠️ Кук недостаточно, получаем свежие...")
            cookies = await get_fresh_cookies()

    if cookies and len(cookies) > 0:
        print(f"🍪 Готово к работе ({len(cookies)} кук)")
        return True
    else:
        print("❌ Не удалось получить куки!")
        return False

# ========== ФУНКЦИЯ ПАРСИНГА ПО GUID ==========

async def parse_case_by_guid(case_guid: str):
    """
    Парсинг карточки дела напрямую по GUID
    Автоматически обновляет куки при ошибке
    """
    global cookies

    case_url = f"https://kad.arbitr.ru/Card/{case_guid}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://kad.arbitr.ru/',
    }

    try:
        response = requests.get(
            case_url,
            headers=headers,
            cookies=cookies,
            impersonate="chrome110",
            timeout=30
        )

        if response.status_code == 403 or response.status_code == 451:
            print(f"⚠️ Ошибка {response.status_code}, куки устарели. Обновляем...")
            await init_cookies(force_refresh=True)
            return await parse_case_by_guid(case_guid)

        if response.status_code != 200:
            return {
                'error': True,
                'message': f'HTTP {response.status_code}',
                'status': 'Ошибка',
                'next_hearing': '—',
                'link': case_url
            }

        soup = BeautifulSoup(response.text, 'html.parser')

        number_elem = soup.select_one('.js-case-header-case_num')
        case_number = number_elem.get_text(strip=True) if number_elem else "Не найден"

        status_elem = soup.select_one('.b-case-header-desc')
        status = status_elem.get_text(strip=True) if status_elem else "Статус не указан"

        hearing_selectors = ['.next-hearing-date', '.hearing-date', '.case-date']
        next_hearing = "Дата не назначена"
        for selector in hearing_selectors:
            elem = soup.select_one(selector)
            if elem:
                next_hearing = elem.get_text(strip=True)
                break

        return {
            'case_number': case_number,
            'status': status,
            'next_hearing': next_hearing,
            'link': case_url,
            'error': False,
            'guid': case_guid
        }

    except Exception as e:
        return {
            'error': True,
            'message': str(e),
            'status': 'Ошибка',
            'next_hearing': '—',
            'link': case_url,
            'guid': case_guid
        }

# ========== ПОИСК GUID ПО НОМЕРУ ДЕЛА ==========

async def find_guid_by_case_number(case_number: str):
    """
    Находит GUID дела по его номеру (используется при добавлении дела)
    """
    global cookies

    case_number = case_number.strip().upper()
    search_url = "https://kad.arbitr.ru/Kad/SearchInstances"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Content-Type': 'application/json',
        'Origin': 'https://kad.arbitr.ru',
        'Referer': 'https://kad.arbitr.ru/',
        'X-Requested-With': 'XMLHttpRequest'
    }

    payload = {
        "Page": 1,
        "Count": 10,
        "Courts": [],
        "DateFrom": "",
        "DateTo": "",
        "CaseNumbers": [case_number],
        "Judges": [],
        "Sides": [],
        "WithVKSInstances": False
    }

    try:
        response = requests.post(
            search_url,
            headers=headers,
            cookies=cookies,
            json=payload,
            impersonate="chrome110",
            timeout=30
        )

        if response.status_code == 403 or response.status_code == 451:
            print("⚠️ Куки устарели, обновляем...")
            await init_cookies(force_refresh=True)
            return await find_guid_by_case_number(case_number)

        if response.status_code != 200:
            return None

        data = response.json()

        if data.get('Results') and len(data['Results']) > 0:
            return data['Results'][0].get('Id')
        else:
            return None

    except Exception as e:
        print(f"❌ Ошибка поиска GUID: {e}")
        return None

print("✅ Модуль парсинга готов!")

# ================================================================
# ОСНОВНОЙ КОД БОТА (ДЛЯ RENDER)
# ================================================================

TOKEN = os.environ.get("TELEGRAM_TOKEN", "8712582808:AAFBZ4VV6Djj7-otwZ_B_yQGyKVgRUwWmdY")

if not TOKEN or TOKEN == "ВАШ_ТОКЕН_СЮДА":
    print("❌ ОШИБКА: Токен не установлен!")
else:
    print(f"✅ Токен загружен: {TOKEN[:20]}...")

# ================================================================
# ФУНКЦИЯ ДЛЯ ГАС
# ================================================================
def generate_gas_link(case_number: str) -> str:
    return f"https://bsr.sudrf.ru/bigs/portal.html?caseNumber={case_number}"

# ================================================================
# БАЗА ДАННЫХ
# ================================================================
conn = sqlite3.connect('cases.db', check_same_thread=False)
cursor = conn.cursor()

# Основная таблица дел
cursor.execute('''
CREATE TABLE IF NOT EXISTS user_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    case_number TEXT,
    case_guid TEXT,
    court_type TEXT DEFAULT 'arbitrazh',
    last_status TEXT,
    last_hearing TEXT,
    last_check TEXT,
    added_at TEXT
)
''')

# Добавляем колонку case_guid, если её нет
try:
    cursor.execute('ALTER TABLE user_cases ADD COLUMN case_guid TEXT')
except sqlite3.OperationalError:
    pass

# Таблица настроек уведомлений
cursor.execute('''
CREATE TABLE IF NOT EXISTS user_settings (
    user_id INTEGER PRIMARY KEY,
    notifications_enabled INTEGER DEFAULT 1,
    notification_mode TEXT DEFAULT 'loud'
)
''')

# Таблица профилей юристов
cursor.execute('''
CREATE TABLE IF NOT EXISTS lawyer_profiles (
    user_id INTEGER PRIMARY KEY,
    full_name TEXT,
    firm_name TEXT,
    email TEXT,
    phone TEXT,
    created_at TEXT
)
''')

# Таблица сроков по делам
cursor.execute('''
CREATE TABLE IF NOT EXISTS case_deadlines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    case_number TEXT,
    deadline_name TEXT,
    deadline_date TEXT,
    status TEXT DEFAULT 'pending',
    completed_at TEXT,
    created_at TEXT
)
''')

# Таблица доступа для клиентов
cursor.execute('''
CREATE TABLE IF NOT EXISTS shared_access (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_number TEXT,
    client_email TEXT,
    access_token TEXT,
    shared_by INTEGER,
    shared_at TEXT
)
''')

# Таблица для AI-аналитики
cursor.execute('''
CREATE TABLE IF NOT EXISTS case_status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    case_number TEXT,
    old_status TEXT,
    new_status TEXT,
    days_in_status INTEGER,
    changed_at TEXT
)
''')

# Таблица для логирования событий
cursor.execute('''
CREATE TABLE IF NOT EXISTS user_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    event_type TEXT,
    case_number TEXT,
    event_date TEXT
)
''')

# Таблица для подписок
cursor.execute('''
CREATE TABLE IF NOT EXISTS user_subscriptions (
    user_id INTEGER PRIMARY KEY,
    subscription_active INTEGER DEFAULT 1,
    trial_start_date TEXT,
    trial_end_date TEXT,
    payment_id TEXT
)
''')

conn.commit()
print("✅ База данных создана/обновлена")

# ================================================================
# ФУНКЦИИ БАЗЫ ДАННЫХ
# ================================================================
def add_case(user_id: int, case_number: str, case_guid: str, court_type: str = 'arbitrazh', status: str = '', hearing: str = ''):
    cursor.execute(
        "INSERT INTO user_cases (user_id, case_number, case_guid, court_type, last_status, last_hearing, added_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, case_number, case_guid, court_type, status, hearing, datetime.now().isoformat())
    )
    conn.commit()

def get_user_cases(user_id: int):
    cursor.execute("SELECT case_number, case_guid, court_type, last_status, last_hearing FROM user_cases WHERE user_id = ?", (user_id,))
    return cursor.fetchall()

def delete_case(user_id: int, case_number: str):
    cursor.execute("DELETE FROM user_cases WHERE user_id = ? AND case_number = ?", (user_id, case_number))
    conn.commit()

def delete_all_cases(user_id: int):
    cursor.execute("DELETE FROM user_cases WHERE user_id = ?", (user_id,))
    conn.commit()

def update_case_status(user_id: int, case_number: str, status: str, hearing: str, case_guid: str = None):
    if case_guid:
        cursor.execute(
            "UPDATE user_cases SET last_status = ?, last_hearing = ?, last_check = ?, case_guid = ? WHERE user_id = ? AND case_number = ?",
            (status, hearing, datetime.now().isoformat(), case_guid, user_id, case_number)
        )
    else:
        cursor.execute(
            "UPDATE user_cases SET last_status = ?, last_hearing = ?, last_check = ? WHERE user_id = ? AND case_number = ?",
            (status, hearing, datetime.now().isoformat(), user_id, case_number)
        )
    conn.commit()

def get_case_guid(user_id: int, case_number: str):
    cursor.execute("SELECT case_guid FROM user_cases WHERE user_id = ? AND case_number = ?", (user_id, case_number))
    row = cursor.fetchone()
    return row[0] if row else None

def get_all_users_cases():
    cursor.execute("SELECT user_id, case_number, case_guid, court_type, last_status, last_hearing FROM user_cases")
    result = {}
    for row in cursor.fetchall():
        if row[0] not in result:
            result[row[0]] = []
        result[row[0]].append({
            'case_number': row[1],
            'case_guid': row[2],
            'court_type': row[3],
            'last_status': row[4],
            'last_hearing': row[5]
        })
    return result

def get_notification_settings(user_id: int) -> tuple:
    cursor.execute("SELECT notifications_enabled, notification_mode FROM user_settings WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row:
        return (row[0] == 1, row[1] if row[1] else 'loud')
    return (True, 'loud')

def set_notification_settings(user_id: int, enabled: bool, mode: str = 'loud'):
    cursor.execute(
        "INSERT OR REPLACE INTO user_settings (user_id, notifications_enabled, notification_mode) VALUES (?, ?, ?)",
        (user_id, 1 if enabled else 0, mode)
    )
    conn.commit()

# Функции для профиля
def save_profile(user_id: int, name: str, firm: str, email: str, phone: str = ''):
    cursor.execute(
        "INSERT OR REPLACE INTO lawyer_profiles (user_id, full_name, firm_name, email, phone, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, name, firm, email, phone, datetime.now().isoformat())
    )
    conn.commit()

def get_profile(user_id: int):
    cursor.execute("SELECT full_name, firm_name, email, phone FROM lawyer_profiles WHERE user_id = ?", (user_id,))
    return cursor.fetchone()

# Функции для сроков
def add_deadline(user_id: int, case_number: str, name: str, date: str):
    cursor.execute(
        "INSERT INTO case_deadlines (user_id, case_number, deadline_name, deadline_date, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, case_number, name, date, datetime.now().isoformat())
    )
    conn.commit()

def get_deadlines(user_id: int, case_number: str):
    cursor.execute(
        "SELECT id, deadline_name, deadline_date, status FROM case_deadlines WHERE user_id = ? AND case_number = ? ORDER BY deadline_date",
        (user_id, case_number)
    )
    return cursor.fetchall()

def complete_deadline(deadline_id: int):
    cursor.execute(
        "UPDATE case_deadlines SET status = 'completed', completed_at = ? WHERE id = ?",
        (datetime.now().isoformat(), deadline_id)
    )
    conn.commit()

def get_deadlines_for_check(user_id: int):
    cursor.execute(
        "SELECT id, case_number, deadline_name, deadline_date FROM case_deadlines WHERE user_id = ? AND status = 'pending'",
        (user_id,)
    )
    return cursor.fetchall()

# Функции для доступа
def save_shared_access(case_number: str, client_email: str, access_token: str, shared_by: int):
    cursor.execute(
        "INSERT INTO shared_access (case_number, client_email, access_token, shared_by, shared_at) VALUES (?, ?, ?, ?, ?)",
        (case_number, client_email, access_token, shared_by, datetime.now().isoformat())
    )
    conn.commit()

# ========== AI-ФУНКЦИИ ==========

def save_status_change(user_id: int, case_number: str, old_status: str, new_status: str, days_in_status: int):
    cursor.execute(
        "INSERT INTO case_status_history (user_id, case_number, old_status, new_status, days_in_status, changed_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, case_number, old_status, new_status, days_in_status, datetime.now().isoformat())
    )
    conn.commit()

async def find_similar_cases(user_id: int, case_number: str) -> dict:
    parts = case_number.split('-')
    if len(parts) < 2:
        return {'total_similar': 0, 'status_distribution': {}, 'examples': []}

    court_code = parts[0]
    year_match = re.search(r'(\d{4})', parts[-1])
    year = year_match.group(1) if year_match else None

    query = "SELECT case_number, last_status FROM user_cases WHERE case_number LIKE ?"
    params = [f"{court_code}-%"]

    if year:
        query += " AND case_number LIKE ?"
        params.append(f"%-{year}")

    cursor.execute(query, params)
    similar = cursor.fetchall()
    similar = [c for c in similar if c[0] != case_number]

    status_counts = {}
    for case, status in similar:
        if status:
            status_counts[status] = status_counts.get(status, 0) + 1

    return {
        'total_similar': len(similar),
        'status_distribution': status_counts,
        'examples': similar[:3]
    }

async def predict_decision_time(user_id: int, case_number: str, current_status: str) -> dict:
    cursor.execute('''
        SELECT new_status, AVG(days_in_status) as avg_days
        FROM case_status_history
        WHERE user_id = ?
        GROUP BY new_status
    ''', (user_id,))

    status_stats = cursor.fetchall()

    if status_stats:
        status_dict = {row[0]: row[1] for row in status_stats}
    else:
        status_dict = {
            "В производстве": 30,
            "Назначено к рассмотрению": 14,
            "Отложено": 21,
            "Рассматривается в первой инстанции": 45,
            "Решение вынесено": 0
        }

    avg_days = status_dict.get(current_status, 30)

    if avg_days > 0:
        predicted_date = datetime.now() + timedelta(days=int(avg_days))
        predicted_date_str = predicted_date.strftime("%d.%m.%Y")
    else:
        predicted_date_str = "Уже скоро"

    confidence = "высокая" if status_stats else "низкая"

    return {
        'predicted_date': predicted_date_str,
        'confidence': confidence,
        'avg_days': avg_days,
        'sources': len(status_stats)
    }

# ========== ФУНКЦИИ ДЛЯ АНАЛИТИКИ ==========

def log_event(user_id: int, event_type: str, case_number: str = ''):
    cursor.execute(
        "INSERT INTO user_events (user_id, event_type, case_number, event_date) VALUES (?, ?, ?, ?)",
        (user_id, event_type, case_number, datetime.now().isoformat())
    )
    conn.commit()

def get_user_stats(user_id: int) -> dict:
    cursor.execute("SELECT COUNT(*) FROM user_events WHERE user_id = ?", (user_id,))
    total_events = cursor.fetchone()[0]

    cursor.execute("SELECT event_type, COUNT(*) FROM user_events WHERE user_id = ? GROUP BY event_type", (user_id,))
    events_by_type = dict(cursor.fetchall())

    cursor.execute('''
        SELECT DATE(event_date), COUNT(*)
        FROM user_events
        WHERE user_id = ?
        GROUP BY DATE(event_date)
        ORDER BY DATE(event_date) DESC
        LIMIT 7
    ''', (user_id,))
    daily_activity = cursor.fetchall()

    return {
        'total_events': total_events,
        'events_by_type': events_by_type,
        'daily_activity': daily_activity
    }

def get_dau() -> int:
    yesterday = (datetime.now() - timedelta(days=1)).isoformat()
    cursor.execute("SELECT COUNT(DISTINCT user_id) FROM user_events WHERE event_date > ?", (yesterday,))
    return cursor.fetchone()[0]

def get_weekly_retention() -> float:
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    two_weeks_ago = (datetime.now() - timedelta(days=14)).isoformat()

    cursor.execute('''
        SELECT DISTINCT user_id FROM user_events
        WHERE event_date BETWEEN ? AND ?
    ''', (two_weeks_ago, week_ago))
    new_users = cursor.fetchall()

    if not new_users:
        return 0.0

    placeholders = ','.join(['?'] * len(new_users))
    cursor.execute(f'''
        SELECT DISTINCT user_id FROM user_events
        WHERE event_date > ? AND user_id IN ({placeholders})
    ''', (week_ago,) + tuple(u[0] for u in new_users))

    returned = cursor.fetchall()
    return len(returned) / len(new_users) * 100

# ========== ФУНКЦИИ ДЛЯ ПОДПИСКИ ==========

def check_subscription(user_id: int) -> tuple:
    cursor.execute("SELECT subscription_active, trial_end_date FROM user_subscriptions WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()

    if not result:
        trial_end = datetime.now() + timedelta(days=7)
        cursor.execute(
            "INSERT INTO user_subscriptions (user_id, subscription_active, trial_start_date, trial_end_date) VALUES (?, 1, ?, ?)",
            (user_id, datetime.now().isoformat(), trial_end.isoformat())
        )
        conn.commit()
        return (True, trial_end, True)

    active, trial_end_str = result
    trial_end = datetime.fromisoformat(trial_end_str) if trial_end_str else None
    is_trial = trial_end and trial_end > datetime.now()
    return (active == 1, trial_end, is_trial)

def activate_subscription(user_id: int, payment_id: str = ''):
    cursor.execute(
        "UPDATE user_subscriptions SET subscription_active = 1, payment_id = ? WHERE user_id = ?",
        (payment_id, user_id)
    )
    conn.commit()

print("✅ Функции БД загружены")

# ================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ================================================================

def parse_date(date_string: str) -> Optional[str]:
    date_string = date_string.strip()
    patterns = [
        (r'^(\d{4})-(\d{1,2})-(\d{1,2})$', '%Y-%m-%d'),
        (r'^(\d{1,2})\.(\d{1,2})\.(\d{4})$', '%d.%m.%Y'),
        (r'^(\d{1,2})\.(\d{1,2})\.(\d{2})$', '%d.%m.%y'),
        (r'^(\d{1,2})/(\d{1,2})/(\d{4})$', '%d/%m/%Y'),
        (r'^(\d{1,2})/(\d{1,2})/(\d{2})$', '%d/%m/%y'),
        (r'^(\d{1,2})-(\d{1,2})-(\d{4})$', '%d-%m-%Y'),
        (r'^(\d{1,2})-(\d{1,2})-(\d{2})$', '%d-%m-%y'),
    ]
    for pattern, date_format in patterns:
        match = re.match(pattern, date_string)
        if match:
            try:
                parsed_date = datetime.strptime(date_string, date_format)
                return parsed_date.strftime('%Y-%m-%d')
            except ValueError:
                continue
    return None

def format_date_for_display(date_str: str) -> str:
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%d.%m.%Y")
    except:
        return date_str

def get_back_button():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Назад в меню", callback_data="back_to_menu")]
    ])

print("✅ Вспомогательные функции загружены")

# ================================================================
# FSM СОСТОЯНИЯ
# ================================================================
class AddCaseStates(StatesGroup):
    waiting_for_case_number = State()
    waiting_for_court_type = State()

class AddDeadlineStates(StatesGroup):
    waiting_for_case_number = State()
    waiting_for_deadline_name = State()
    waiting_for_deadline_date = State()
    waiting_for_confirmation = State()

class ProfileStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_firm = State()
    waiting_for_email = State()
    waiting_for_phone = State()

print("✅ FSM состояния загружены")

# ================================================================
# КОМАНДЫ БОТА
# ================================================================
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ---------- НАВИГАЦИЯ И ГЛАВНОЕ МЕНЮ ----------
@dp.message(Command("start"))
async def start_command(message: types.Message):
    user_id = message.from_user.id
    active, trial_end, is_trial = check_subscription(user_id)

    trial_info = ""
    if is_trial and trial_end:
        days_left = (trial_end - datetime.now()).days
        trial_info = f"\n\n💎 *Пробный период:* {days_left} дней осталось"
    elif not active:
        trial_info = "\n\n⚠️ *Пробный период закончился.* Оформите подписку через `/subscribe`"

    await message.answer(
        "🤖 *Юридический бот-мониторинг*\n\n"
        "Я помогаю юристам следить за движением судебных дел:\n"
        "• 🏛️ Арбитражные суды (КАД) — *реальный парсинг*\n"
        "• ⚖️ Суды общей юрисдикции (ГАС) — *полуавтоматический режим*\n\n"
        "📌 *Нажмите /menu для открытия главного меню*" + trial_info,
        parse_mode="Markdown"
    )
    log_event(user_id, "start")

@dp.message(Command("menu"))
async def main_menu(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 Библиотека дел", callback_data="menu_library"), InlineKeyboardButton(text="➕ Добавить дело", callback_data="menu_add")],
        [InlineKeyboardButton(text="🔄 Проверить все", callback_data="menu_check"), InlineKeyboardButton(text="📊 Статистика", callback_data="menu_stats")],
        [InlineKeyboardButton(text="📅 Управление сроками", callback_data="menu_deadlines"), InlineKeyboardButton(text="📈 Ход дела", callback_data="menu_progress")],
        [InlineKeyboardButton(text="🔔 Уведомления", callback_data="menu_notifications"), InlineKeyboardButton(text="👤 Мой профиль", callback_data="menu_profile")],
        [InlineKeyboardButton(text="🤖 AI-аналитика", callback_data="menu_insights"), InlineKeyboardButton(text="📊 Аналитика", callback_data="menu_analytics")],
        [InlineKeyboardButton(text="📄 Экспорт PDF", callback_data="menu_export"), InlineKeyboardButton(text="💎 Подписка", callback_data="menu_subscribe")],
        [InlineKeyboardButton(text="❓ Помощь", callback_data="menu_help")]
    ])
    await message.answer("🏠 *Главное меню*\n\nВыберите действие:", parse_mode="Markdown", reply_markup=keyboard)
    log_event(message.from_user.id, "menu")

# ---------- ОБРАБОТЧИК КНОПКИ "НАЗАД" ----------
@dp.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await main_menu(callback.message)
    await callback.answer()

# ---------- ОБРАБОТЧИКИ ГЛАВНОГО МЕНЮ ----------
@dp.callback_query(lambda c: c.data == "menu_library")
async def menu_library(callback: types.CallbackQuery):
    await library_command(callback.message)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_add")
async def menu_add(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("📝 Введите номер дела:", reply_markup=get_back_button())
    await state.set_state(AddCaseStates.waiting_for_case_number)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_check")
async def menu_check(callback: types.CallbackQuery):
    await check_cases_command(callback.message)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_stats")
async def menu_stats_cmd(callback: types.CallbackQuery):
    await stats_command(callback.message)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_deadlines")
async def menu_deadlines(callback: types.CallbackQuery):
    await callback.message.answer(
        "📅 *Управление сроками*\n\n"
        "• `/deadline НОМЕР` — добавить срок\n"
        "• `/progress НОМЕР` — ход дела\n"
        "• `/complete ID` — отметить выполненный",
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_progress")
async def menu_progress_cmd(callback: types.CallbackQuery):
    await callback.message.answer("📈 Отправьте: `/progress НОМЕР_ДЕЛА`", parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_notifications")
async def menu_notifications(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔔 Громкий режим", callback_data="notify_loud")],
        [InlineKeyboardButton(text="🔕 Тихий режим", callback_data="notify_silent")],
        [InlineKeyboardButton(text="🔇 Выключить", callback_data="notify_off")],
        [InlineKeyboardButton(text="🔊 Включить", callback_data="notify_on")],
        [InlineKeyboardButton(text="🏠 Назад", callback_data="back_to_menu")]
    ])
    await callback.message.answer("🔔 *Настройка уведомлений*", parse_mode="Markdown", reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_profile")
async def menu_profile_cmd(callback: types.CallbackQuery):
    await profile_command(callback.message)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_share")
async def menu_share_cmd(callback: types.CallbackQuery):
    await callback.message.answer(
        "📧 *Передать доступ*\n\nФормат: `/share НОМЕР_ДЕЛА EMAIL`\nПример: `/share А40-12345/2026 client@example.com`",
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_insights")
async def menu_insights_cmd(callback: types.CallbackQuery):
    await insights_command(callback.message)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_analytics")
async def menu_analytics_cmd(callback: types.CallbackQuery):
    await analytics_command(callback.message)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_export")
async def menu_export_cmd(callback: types.CallbackQuery):
    await callback.message.answer("📄 Для экспорта дела в PDF используйте: `/export НОМЕР_ДЕЛА`", parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_subscribe")
async def menu_subscribe_cmd(callback: types.CallbackQuery):
    await subscribe_command(callback.message)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_help")
async def menu_help_cmd(callback: types.CallbackQuery):
    await help_command(callback.message)
    await callback.answer()

# ---------- НАСТРОЙКА УВЕДОМЛЕНИЙ ----------
@dp.callback_query(lambda c: c.data == "notify_loud")
async def notify_loud(callback: types.CallbackQuery):
    set_notification_settings(callback.from_user.id, True, 'loud')
    await callback.message.answer("🔔 *Громкий режим включен*", parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "notify_silent")
async def notify_silent(callback: types.CallbackQuery):
    set_notification_settings(callback.from_user.id, True, 'silent')
    await callback.message.answer("🔕 *Тихий режим включен*", parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "notify_on")
async def notify_on_cb(callback: types.CallbackQuery):
    mode = get_notification_settings(callback.from_user.id)[1]
    set_notification_settings(callback.from_user.id, True, mode)
    await callback.message.answer("🔔 *Уведомления включены*", parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "notify_off")
async def notify_off_cb(callback: types.CallbackQuery):
    set_notification_settings(callback.from_user.id, False, 'silent')
    await callback.message.answer("🔇 *Уведомления выключены*", parse_mode="Markdown")
    await callback.answer()

# ---------- БИБЛИОТЕКА ДЕЛ ----------
@dp.message(Command("library"))
async def library_command(message: types.Message):
    user_id = message.from_user.id
    cases = get_user_cases(user_id)
    if not cases:
        await message.answer("📚 *Библиотека дел*\n\n📭 *В вашей библиотеке нет дел*\n\n➕ Добавьте дело через /add", parse_mode="Markdown")
        return
    arb_cases = [c for c in cases if c[2] == 'arbitrazh']
    gas_cases = [c for c in cases if c[2] == 'gas']
    response = "📚 *Библиотека дел*\n\n"
    if arb_cases:
        response += "🏛️ *КАД (Арбитражные суды)*\n"
        for case in arb_cases:
            status_icon = "🟢" if case[3] == "В производстве" else "🔵"
            response += f"{status_icon} `{case[0]}`\n"
            if case[3]:
                response += f"   └ 📌 {case[3][:40]}\n"
        response += "\n"
    if gas_cases:
        response += "⚖️ *ГАС (Суды общей юрисдикции)*\n"
        for case in gas_cases:
            response += f"📄 `{case[0]}`\n"
        response += "\n"
    response += f"📊 *Всего:* {len(cases)} дел"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить дело", callback_data="menu_add")],
        [InlineKeyboardButton(text="🏠 Назад", callback_data="back_to_menu")]
    ])
    await message.answer(response, parse_mode="Markdown", reply_markup=keyboard)
    log_event(user_id, "library")

@dp.message(Command("list"))
async def list_cases_command(message: types.Message):
    user_id = message.from_user.id
    cases = get_user_cases(user_id)
    if not cases:
        await message.answer("📭 У вас пока нет дел. Нажмите `/add`", parse_mode="Markdown")
        return
    response = "📋 *Ваши дела:*\n\n"
    for case in cases:
        response += f"• `{case[0]}`\n"
        if case[3]:
            response += f"  📌 {case[3]}\n"
    response += f"\n📊 Всего: {len(cases)} дел"
    await message.answer(response, parse_mode="Markdown", reply_markup=get_back_button())
    log_event(user_id, "list")

# ---------- ДОБАВЛЕНИЕ ДЕЛА ----------
@dp.message(Command("add"))
async def add_case_start(message: types.Message, state: FSMContext):
    await state.set_state(AddCaseStates.waiting_for_case_number)
    await message.answer(
        "📝 *Добавление нового дела*\n\n"
        "Введите номер дела.\n\n"
        "Примеры:\n"
        "• `А40-12345/2026` (арбитраж)\n"
        "• `2-1234/2026` (общая юрисдикция)\n\n"
        "Для отмены отправьте `/cancel`",
        parse_mode="Markdown",
        reply_markup=get_back_button()
    )

@dp.message(Command("cancel"))
async def cancel_add(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Добавление дела отменено", reply_markup=get_back_button())

@dp.message(AddCaseStates.waiting_for_case_number)
async def process_case_number(message: types.Message, state: FSMContext):
    case_number = message.text.strip()
    if len(case_number) < 5:
        await message.answer("❌ Номер дела слишком короткий. Попробуйте еще раз или /cancel", reply_markup=get_back_button())
        return
    await state.update_data(case_number=case_number)
    await state.set_state(AddCaseStates.waiting_for_court_type)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏛️ Арбитражный суд (КАД)", callback_data="court_arbitrazh")],
        [InlineKeyboardButton(text="⚖️ Суд общей юрисдикции (ГАС)", callback_data="court_gas")],
        [InlineKeyboardButton(text="🏠 Назад в меню", callback_data="back_to_menu")]
    ])
    await message.answer(f"📌 *Дело:* `{case_number}`\n\nВыберите тип суда:", parse_mode="Markdown", reply_markup=keyboard)

@dp.callback_query(lambda c: c.data.startswith("court_"))
async def process_court_type(callback: types.CallbackQuery, state: FSMContext):
    court_type = callback.data.replace("court_", "")
    user_data = await state.get_data()
    case_number = user_data.get('case_number')
    user_id = callback.from_user.id

    if court_type == 'arbitrazh':
        await callback.message.edit_text(f"🔍 Ищу дело `{case_number}` в КАД...", parse_mode="Markdown")
        case_guid = await find_guid_by_case_number(case_number)

        if not case_guid:
            await callback.message.edit_text(f"❌ Дело `{case_number}` не найдено в КАД. Проверьте номер.", parse_mode="Markdown")
            await state.clear()
            await callback.answer()
            return

        result = await parse_case_by_guid(case_guid)
        if result.get('error'):
            await callback.message.edit_text(f"❌ Ошибка при загрузке дела: {result.get('message')}", parse_mode="Markdown")
            await state.clear()
            await callback.answer()
            return

        add_case(user_id, result['case_number'], case_guid, court_type, result['status'], result['next_hearing'])

        await callback.message.edit_text(
            f"✅ *Дело добавлено!* 🏛️\n\n"
            f"📌 *Номер:* `{result['case_number']}`\n"
            f"📋 *Статус:* {result['status']}\n"
            f"📅 *Заседание:* {result['next_hearing']}\n"
            f"🔗 [Ссылка на карточку]({result['link']})",
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📅 Добавить сроки", callback_data=f"add_deadline_{result['case_number']}")],
            [InlineKeyboardButton(text="🏠 В меню", callback_data="back_to_menu")]
        ])
        await callback.message.answer(
            "📅 *Анализ сроков*\n\nРекомендуем добавить процессуальные сроки по делу.",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        log_event(user_id, "add_case", result['case_number'])
    else:
        gas_link = generate_gas_link(case_number)
        add_case(user_id, case_number, None, court_type)
        await callback.message.edit_text(
            f"✅ *Дело добавлено!* ⚖️\n\n"
            f"📌 *Номер:* `{case_number}`\n"
            f"📋 *Режим:* Полуавтоматический\n\n"
            f"🔗 *Ссылка для проверки:*\n{gas_link}",
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        log_event(user_id, "add_case_gas", case_number)
    await state.clear()
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("add_deadline_"))
async def add_deadline_from_button(callback: types.CallbackQuery, state: FSMContext):
    case_number = callback.data.replace("add_deadline_", "")
    await state.update_data(case_number=case_number)
    await state.set_state(AddDeadlineStates.waiting_for_deadline_name)
    await callback.message.answer(
        f"📌 *Дело:* `{case_number}`\n\nВведите название срока:",
        parse_mode="Markdown",
        reply_markup=get_back_button()
    )
    await callback.answer()

# ---------- ПРОВЕРКА ДЕЛ ----------
@dp.message(Command("check"))
async def check_cases_command(message: types.Message):
    user_id = message.from_user.id
    cases = get_user_cases(user_id)
    if not cases:
        await message.answer("📭 У вас нет дел в мониторинге", reply_markup=get_back_button())
        return

    await message.answer("🔍 *Начинаю проверку ваших дел...*", parse_mode="Markdown")
    updated_count = 0
    for case_number, case_guid, court_type, last_status, last_hearing in cases:
        if court_type == 'arbitrazh':
            if not case_guid:
                await message.answer(f"⚠️ Для дела `{case_number}` отсутствует GUID. Удалите и добавьте заново.", parse_mode="Markdown")
                continue
            result = await parse_case_by_guid(case_guid)
            if result.get('error'):
                await message.answer(f"⚠️ Ошибка проверки `{case_number}`: {result.get('message')}", parse_mode="Markdown")
                continue
            if result['status'] != last_status or result['next_hearing'] != last_hearing:
                update_case_status(user_id, case_number, result['status'], result['next_hearing'], case_guid)
                await message.answer(
                    f"🔄 *Изменение по делу* `{case_number}`\n\n"
                    f"📋 Новый статус: {result['status']}\n"
                    f"📅 Заседание: {result['next_hearing']}\n"
                    f"🔗 [Ссылка]({result['link']})",
                    parse_mode="Markdown",
                    disable_web_page_preview=True
                )
                updated_count += 1
            await asyncio.sleep(0.5)
    await message.answer(f"✅ *Проверка завершена* (обновлено: {updated_count})", parse_mode="Markdown", reply_markup=get_back_button())
    log_event(user_id, "check_cases")

@dp.message(Command("status"))
async def status_command(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Укажите номер дела.\nПример: `/status А40-12345/2026`", parse_mode="Markdown", reply_markup=get_back_button())
        return
    case_number = parts[1].strip()
    user_id = message.from_user.id
    case_guid = get_case_guid(user_id, case_number)
    if not case_guid:
        await message.answer(f"❌ Дело `{case_number}` не найдено в вашей библиотеке или отсутствует GUID.", parse_mode="Markdown", reply_markup=get_back_button())
        return
    await message.answer(f"🔍 *Проверяю дело {case_number}...*", parse_mode="Markdown")
    result = await parse_case_by_guid(case_guid)
    if result.get('error'):
        await message.answer(f"⚠️ Ошибка: {result.get('message')}", parse_mode="Markdown", reply_markup=get_back_button())
    else:
        await message.answer(
            f"⚖️ *Результат проверки*\n\n"
            f"📌 *Дело:* `{result['case_number']}`\n"
            f"📋 *Статус:* {result['status']}\n"
            f"📅 *Заседание:* {result['next_hearing']}\n"
            f"🔗 [Ссылка на карточку]({result['link']})",
            parse_mode="Markdown",
            disable_web_page_preview=True,
            reply_markup=get_back_button()
        )
    log_event(user_id, "status_check", case_number)

# ---------- УДАЛЕНИЕ ДЕЛ ----------
@dp.message(Command("remove"))
async def remove_case_command(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Укажите номер дела.\nПример: `/remove А40-12345/2026`", parse_mode="Markdown", reply_markup=get_back_button())
        return
    case_number = parts[1].strip()
    user_id = message.from_user.id
    delete_case(user_id, case_number)
    await message.answer(f"🗑️ Дело `{case_number}` удалено из мониторинга", parse_mode="Markdown", reply_markup=get_back_button())
    log_event(user_id, "remove_case", case_number)

@dp.message(Command("clear_all"))
async def clear_all_command(message: types.Message):
    user_id = message.from_user.id
    cases = get_user_cases(user_id)
    if not cases:
        await message.answer("📭 У вас нет дел для удаления", reply_markup=get_back_button())
        return
    delete_all_cases(user_id)
    await message.answer(f"🗑️ *Очищено!*\n\nУдалено дел: *{len(cases)}*", parse_mode="Markdown", reply_markup=get_back_button())
    log_event(user_id, "clear_all")

# ---------- УПРАВЛЕНИЕ СРОКАМИ ----------
@dp.message(Command("deadline"))
async def add_deadline_start(message: types.Message, state: FSMContext):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("📅 *Добавление срока по делу*\n\nУкажите номер дела:\nПример: `/deadline А40-12345/2026`", parse_mode="Markdown", reply_markup=get_back_button())
        return
    case_number = parts[1].strip()
    cases = get_user_cases(message.from_user.id)
    if not any(c[0] == case_number for c in cases):
        await message.answer(f"❌ Дело `{case_number}` не найдено в вашей библиотеке", parse_mode="Markdown", reply_markup=get_back_button())
        return
    await state.update_data(case_number=case_number)
    await state.set_state(AddDeadlineStates.waiting_for_deadline_name)
    await message.answer(f"📌 *Дело:* `{case_number}`\n\nВведите название срока:", parse_mode="Markdown", reply_markup=get_back_button())

@dp.message(AddDeadlineStates.waiting_for_deadline_name)
async def process_deadline_name(message: types.Message, state: FSMContext):
    await state.update_data(deadline_name=message.text.strip())
    await state.set_state(AddDeadlineStates.waiting_for_deadline_date)
    await message.answer("📅 Введите дату срока\n\nДопустимые форматы:\n• `2026-06-20`\n• `20.06.2026`\n• `20/06/2026`\n• `20-06-2026`\n\nПример: `20.06.2026`", parse_mode="Markdown", reply_markup=get_back_button())

@dp.message(AddDeadlineStates.waiting_for_deadline_date)
async def process_deadline_date(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    case_number = user_data['case_number']
    deadline_name = user_data['deadline_name']
    raw_date = message.text.strip()
    deadline_date = parse_date(raw_date)
    if not deadline_date:
        await message.answer("❌ *Неверный формат даты*\n\nПример: `20.06.2026`", parse_mode="Markdown", reply_markup=get_back_button())
        return
    today = datetime.now().date()
    parsed_date = datetime.strptime(deadline_date, "%Y-%m-%d").date()
    if parsed_date < today:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, добавить", callback_data="confirm_deadline_yes")],
            [InlineKeyboardButton(text="❌ Нет, ввести заново", callback_data="confirm_deadline_no")],
            [InlineKeyboardButton(text="🏠 Назад в меню", callback_data="back_to_menu")]
        ])
        await state.update_data(deadline_date=deadline_date)
        await state.set_state(AddDeadlineStates.waiting_for_confirmation)
        await message.answer(f"⚠️ *Внимание!*\n\nУказанная дата `{format_date_for_display(deadline_date)}` уже прошла.\n\nВы уверены, что хотите добавить этот срок?", parse_mode="Markdown", reply_markup=keyboard)
        return
    add_deadline(message.from_user.id, case_number, deadline_name, deadline_date)
    await state.clear()
    await message.answer(f"✅ *Срок добавлен!*\n\n📌 Дело: `{case_number}`\n📋 Срок: {deadline_name}\n📅 Дата: {format_date_for_display(deadline_date)}\n\n🔔 Бот напомнит за 3 дня до срока.", parse_mode="Markdown", reply_markup=get_back_button())
    log_event(message.from_user.id, "add_deadline", case_number)

@dp.callback_query(lambda c: c.data == "confirm_deadline_yes")
async def confirm_deadline_yes(callback: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    add_deadline(callback.from_user.id, user_data['case_number'], user_data['deadline_name'], user_data['deadline_date'])
    await state.clear()
    await callback.message.edit_text("✅ *Срок добавлен!* (с просроченной датой)", parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "confirm_deadline_no")
async def confirm_deadline_no(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddDeadlineStates.waiting_for_deadline_date)
    await callback.message.edit_text("📅 Введите дату заново:", reply_markup=get_back_button())
    await callback.answer()

# ---------- ПРОГРЕСС С AI-АНАЛИТИКОЙ ----------
@dp.message(Command("progress"))
async def show_progress(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Укажите номер дела.\nПример: `/progress А40-12345/2026`", parse_mode="Markdown", reply_markup=get_back_button())
        return
    case_number = parts[1].strip()
    user_id = message.from_user.id
    cursor.execute("SELECT last_status, court_type FROM user_cases WHERE user_id = ? AND case_number = ?", (user_id, case_number))
    case_info = cursor.fetchone()
    if not case_info:
        await message.answer(f"❌ Дело `{case_number}` не найдено в вашей библиотеке", parse_mode="Markdown", reply_markup=get_back_button())
        return
    last_status = case_info[0] or "В производстве"
    deadlines = get_deadlines(user_id, case_number)
    today = datetime.now().date()
    response = f"📊 *Ход дела* `{case_number}`\n\n🏛️ *Текущий статус:* {last_status}\n\n"
    if not deadlines:
        response += "📭 *Нет добавленных сроков*\n\n➕ Добавьте сроки через `/deadline`"
    else:
        total = len(deadlines)
        completed = len([d for d in deadlines if d[3] == 'completed'])
        progress_percent = int((completed / total) * 20) if total > 0 else 0
        bar = "🟢" * progress_percent + "⚪" * (20 - progress_percent)
        response += f"`[{bar}]`\n📊 Выполнено: {completed}/{total}\n\n"
        for deadline_id, name, date_str, status in deadlines:
            d_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            formatted_date = format_date_for_display(date_str)
            icon = "✅" if status == "completed" else ("🔴" if d_date == today else ("⚠️" if d_date < today else "⏳"))
            response += f"{icon} **{name}**\n   📅 {formatted_date}\n\n"

    # AI-аналитика
    response += "\n---\n🤖 *AI-аналитика*\n\n"

    similar = await find_similar_cases(user_id, case_number)
    if similar['total_similar'] > 0:
        response += f"📊 *Похожие дела:* найдено {similar['total_similar']}\n"
        if similar['status_distribution']:
            most_common = max(similar['status_distribution'], key=similar['status_distribution'].get)
            response += f"   • Чаще всего они в статусе: *{most_common}*\n"
    else:
        response += "📊 *Похожие дела:* пока нет данных\n"

    prediction = await predict_decision_time(user_id, case_number, last_status)
    if prediction['predicted_date']:
        emoji = "🎯" if prediction['confidence'] == "высокая" else "📌"
        response += f"{emoji} *Прогноз решения:* {prediction['predicted_date']}\n"
        response += f"   (уверенность: {prediction['confidence']}, на основе {prediction['sources']} дел)\n"
    else:
        response += "🎯 *Прогноз решения:* накопление статистики...\n"

    if last_status in ["В производстве", "Рассматривается в первой инстанции"]:
        response += "\n💡 *Совет:* Добавьте напоминание о сроках через `/deadline`"

    await message.answer(response, parse_mode="Markdown", reply_markup=get_back_button())
    log_event(user_id, "progress", case_number)

@dp.message(Command("complete"))
async def complete_deadline_command(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Укажите ID срока.\nПример: `/complete 5`", parse_mode="Markdown", reply_markup=get_back_button())
        return
    try:
        complete_deadline(int(parts[1].strip()))
        await message.answer(f"✅ Срок #{parts[1]} отмечен как выполненный!", parse_mode="Markdown", reply_markup=get_back_button())
        log_event(message.from_user.id, "complete_deadline")
    except ValueError:
        await message.answer("❌ ID срока должен быть числом", parse_mode="Markdown", reply_markup=get_back_button())

# ---------- ПРОФИЛЬ ЮРИСТА ----------
@dp.message(Command("profile"))
async def profile_command(message: types.Message):
    profile = get_profile(message.from_user.id)
    if profile:
        await message.answer(f"👤 *Ваш профиль*\n\n📛 Имя: {profile[0]}\n🏢 Фирма: {profile[1]}\n📧 Email: {profile[2]}\n📞 Телефон: {profile[3] or 'не указан'}\n\nДля изменения: `/edit_profile`", parse_mode="Markdown", reply_markup=get_back_button())
    else:
        await message.answer("👤 *Заполните профиль*\n\nОтправьте: `/profile Имя | Фирма | email | телефон`\n\nПример: `/profile Иванов И.И. | ЮрФирма | ivanov@law.ru | +79001234567`", parse_mode="Markdown", reply_markup=get_back_button())

@dp.message(Command("edit_profile"))
async def edit_profile_start(message: types.Message, state: FSMContext):
    await state.set_state(ProfileStates.waiting_for_name)
    await message.answer("📝 *Редактирование профиля*\n\nВведите ваше ФИО:", parse_mode="Markdown", reply_markup=get_back_button())

@dp.message(ProfileStates.waiting_for_name)
async def edit_profile_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(ProfileStates.waiting_for_firm)
    await message.answer("🏢 Введите название вашей фирмы:", reply_markup=get_back_button())

@dp.message(ProfileStates.waiting_for_firm)
async def edit_profile_firm(message: types.Message, state: FSMContext):
    await state.update_data(firm=message.text.strip())
    await state.set_state(ProfileStates.waiting_for_email)
    await message.answer("📧 Введите ваш email:", reply_markup=get_back_button())

@dp.message(ProfileStates.waiting_for_email)
async def edit_profile_email(message: types.Message, state: FSMContext):
    await state.update_data(email=message.text.strip())
    await state.set_state(ProfileStates.waiting_for_phone)
    await message.answer("📞 Введите ваш телефон (или /skip чтобы пропустить):", reply_markup=get_back_button())

@dp.message(Command("skip"))
async def skip_phone(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    save_profile(message.from_user.id, user_data.get('name', ''), user_data.get('firm', ''), user_data.get('email', ''), '')
    await state.clear()
    await message.answer("✅ Профиль сохранен!", parse_mode="Markdown", reply_markup=get_back_button())

@dp.message(ProfileStates.waiting_for_phone)
async def edit_profile_phone(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    save_profile(message.from_user.id, user_data.get('name', ''), user_data.get('firm', ''), user_data.get('email', ''), message.text.strip())
    await state.clear()
    await message.answer("✅ Профиль сохранен!", parse_mode="Markdown", reply_markup=get_back_button())

# ---------- ПЕРЕДАЧА ДОСТУПА КЛИЕНТУ ----------
@dp.message(Command("share"))
async def share_case_command(message: types.Message):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("📧 *Передать доступ клиенту*\n\nФормат: `/share НОМЕР_ДЕЛА EMAIL_КЛИЕНТА`\n\nПример: `/share А40-12345/2026 client@example.com`", parse_mode="Markdown", reply_markup=get_back_button())
        return
    case_number = parts[1].strip()
    client_email = parts[2].strip()
    user_id = message.from_user.id
    cases = get_user_cases(user_id)
    if not any(c[0] == case_number for c in cases):
        await message.answer(f"❌ Дело `{case_number}` не найдено в вашей библиотеке", parse_mode="Markdown", reply_markup=get_back_button())
        return
    profile = get_profile(user_id)
    lawyer_name = profile[0] if profile else "Юрист"
    access_token = secrets.token_urlsafe(32)
    save_shared_access(case_number, client_email, access_token, user_id)
    client_link = f"https://t.me/{bot.username}?start=access_{access_token}"
    await message.answer(f"✅ *Доступ передан!*\n\n📌 Дело: `{case_number}`\n📧 Клиент: `{client_email}`\n\n🔗 Ссылка для клиента:\n`{client_link}`\n\n⚠️ В демо-версии email не отправляется.", parse_mode="Markdown", reply_markup=get_back_button())
    log_event(user_id, "share_case", case_number)

# ---------- СТАТИСТИКА ----------
@dp.message(Command("stats"))
async def stats_command(message: types.Message):
    user_id = message.from_user.id
    cases = get_user_cases(user_id)
    total = len(cases)
    arb_count = len([c for c in cases if c[2] == 'arbitrazh'])
    gas_count = len([c for c in cases if c[2] == 'gas'])
    cursor.execute("SELECT COUNT(*) FROM case_deadlines WHERE user_id = ?", (user_id,))
    deadlines_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM case_status_history WHERE user_id = ?", (user_id,))
    history_count = cursor.fetchone()[0]
    enabled, mode = get_notification_settings(user_id)
    notification_status = "включены ✅" if enabled else "выключены 🔕"
    notification_mode = "громкий 🔔" if mode == 'loud' else "тихий 🔕"
    profile = get_profile(user_id)
    await message.answer(f"📊 *Ваша статистика*\n\n📋 Всего дел: *{total}*\n🏛️ Арбитражных: *{arb_count}*\n⚖️ Общей юрисдикции: *{gas_count}*\n📅 Всего сроков: *{deadlines_count}*\n🤖 Записей для AI: *{history_count}*\n\n🔔 Уведомления: {notification_status}\n📢 Режим: {notification_mode}\n\n👤 Профиль: {'✅ заполнен' if profile else '❌ не заполнен'}", parse_mode="Markdown", reply_markup=get_back_button())

# ---------- AI-АНАЛИТИКА ----------
@dp.message(Command("insights"))
async def insights_command(message: types.Message):
    user_id = message.from_user.id
    cases = get_user_cases(user_id)

    if not cases:
        await message.answer("📭 У вас пока нет дел. Добавьте через `/add`", parse_mode="Markdown", reply_markup=get_back_button())
        return

    total_cases = len(cases)
    completed = len([c for c in cases if c[3] and ("завершено" in c[3] or "решение" in c[3])])
    in_progress = total_cases - completed

    cursor.execute('SELECT AVG(days_in_status) FROM case_status_history WHERE user_id = ?', (user_id,))
    avg_duration_raw = cursor.fetchone()[0]
    avg_duration = int(avg_duration_raw) if avg_duration_raw else 30

    active_predictions = []
    for case in cases:
        if case[3] and "завершено" not in case[3] and "решение" not in case[3]:
            pred = await predict_decision_time(user_id, case[0], case[3])
            active_predictions.append(pred)

    response = (
        "🤖 *AI-аналитика по вашим делам*\n\n"
        f"📊 *Статистика:* {total_cases} дел ({in_progress} в работе, {completed} завершено)\n"
        f"📅 *Средняя длительность:* {avg_duration} дней\n\n"
    )

    if active_predictions:
        avg_prediction = sum(p['avg_days'] for p in active_predictions) / len(active_predictions)
        soonest = min(active_predictions, key=lambda x: x['avg_days'])
        response += f"🎯 *Ближайший прогноз решения:*\n   • Ожидается: {soonest['predicted_date']}\n"
        response += f"   • Уверенность: {soonest['confidence']}\n\n"
    else:
        response += "🎯 *Прогноз решений:* пока нет активных дел\n\n"

    response += (
        "💡 *Рекомендации:*\n"
        "• Добавляйте сроки через `/deadline`, чтобы AI точнее предсказывал\n"
        "• Чем больше дел вы отслеживаете, тем умнее становится аналитика\n"
        "• Используйте `/progress` для детального AI-анализа по каждому делу"
    )

    await message.answer(response, parse_mode="Markdown", reply_markup=get_back_button())

# ---------- АНАЛИТИКА ПОЛЬЗОВАТЕЛЯ ----------
@dp.message(Command("analytics"))
async def analytics_command(message: types.Message):
    user_id = message.from_user.id

    active, trial_end, is_trial = check_subscription(user_id)
    stats = get_user_stats(user_id)
    dau = get_dau()
    retention = get_weekly_retention()

    response = (
        "📊 *Аналитика использования*\n\n"
        f"📈 *Ваша активность:*\n"
        f"   • Всего действий: {stats['total_events']}\n"
        f"   • Добавлений дел: {stats['events_by_type'].get('add_case', 0)}\n"
        f"   • Проверок: {stats['events_by_type'].get('check_cases', 0)}\n"
        f"   • Удалений: {stats['events_by_type'].get('remove_case', 0)}\n\n"
        f"📅 *Активность за последние 7 дней:*\n"
    )

    for date, count in stats['daily_activity'][:7]:
        response += f"   • {date[:10]}: {count} действий\n"

    response += (
        f"\n📊 *Общая аналитика платформы:*\n"
        f"   • DAU (активных за сутки): {dau}\n"
        f"   • Retention (возвращаемость): {retention:.1f}%\n\n"
    )

    if is_trial:
        days_left = (trial_end - datetime.now()).days
        response += (
            f"💎 *Пробный период:* активен\n"
            f"   • Осталось дней: {days_left}\n"
            f"   • Подписка: 500 руб/мес — `/subscribe`"
        )
    elif active:
        response += f"💎 *Подписка:* активна"
    else:
        response += "💎 *Подписка:* не активна. Оформите через `/subscribe`"

    await message.answer(response, parse_mode="Markdown", reply_markup=get_back_button())

# ---------- ЭКСПОРТ В PDF ----------
@dp.message(Command("export"))
async def export_pdf_command(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Укажите номер дела.\nПример: `/export А40-12345/2026`", parse_mode="Markdown", reply_markup=get_back_button())
        return

    case_number = parts[1].strip()
    user_id = message.from_user.id

    active, trial_end, is_trial = check_subscription(user_id)
    if not active and not is_trial:
        await message.answer(
            "⚠️ *Функция доступна только по подписке*\n\n"
            "Оформите подписку через `/subscribe` (500 Stars/мес)",
            parse_mode="Markdown",
            reply_markup=get_back_button()
        )
        return

    cursor.execute("SELECT case_number, case_guid, last_status, last_hearing, added_at FROM user_cases WHERE user_id = ? AND case_number = ?",
                   (user_id, case_number))
    case = cursor.fetchone()

    if not case:
        await message.answer(f"❌ Дело `{case_number}` не найдено", parse_mode="Markdown", reply_markup=get_back_button())
        return

    deadlines = get_deadlines(user_id, case_number)
    cursor.execute("SELECT old_status, new_status, changed_at FROM case_status_history WHERE user_id = ? AND case_number = ? ORDER BY changed_at",
                   (user_id, case_number))
    history = cursor.fetchall()

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        import io

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm)
        styles = getSampleStyleSheet()
        story = []

        title_style = ParagraphStyle('TitleStyle', parent=styles['Title'], fontSize=16, alignment=1, spaceAfter=20)
        story.append(Paragraph(f"Отчёт по делу {case[0]}", title_style))
        story.append(Spacer(1, 10))

        story.append(Paragraph(f"<b>Номер дела:</b> {case[0]}", styles['Normal']))
        story.append(Paragraph(f"<b>Текущий статус:</b> {case[2] or 'Не указан'}", styles['Normal']))
        story.append(Paragraph(f"<b>Следующее заседание:</b> {case[3] or 'Не назначено'}", styles['Normal']))
        story.append(Paragraph(f"<b>Дата добавления:</b> {datetime.fromisoformat(case[4]).strftime('%d.%m.%Y')}", styles['Normal']))
        story.append(Spacer(1, 15))

        if deadlines:
            story.append(Paragraph("<b>Процессуальные сроки:</b>", styles['Heading2']))
            story.append(Spacer(1, 5))
            deadline_text = ""
            for _, name, date_str, status in deadlines:
                icon = "✅" if status == "completed" else "⏳"
                deadline_text += f"{icon} {name}: {format_date_for_display(date_str)}\n"
            story.append(Paragraph(deadline_text.replace('\n', '<br/>'), styles['Normal']))
            story.append(Spacer(1, 15))

        if history:
            story.append(Paragraph("<b>История изменений статуса:</b>", styles['Heading2']))
            story.append(Spacer(1, 5))
            hist_text = ""
            for old, new, changed_at in history:
                date = datetime.fromisoformat(changed_at).strftime('%d.%m.%Y')
                hist_text += f"• {date}: {old} → {new}\n"
            story.append(Paragraph(hist_text.replace('\n', '<br/>'), styles['Normal']))

        story.append(Spacer(1, 30))
        story.append(Paragraph(f"Отчёт сгенерирован {datetime.now().strftime('%d.%m.%Y %H:%M')}", styles['Italic']))

        doc.build(story)
        pdf_data = buffer.getvalue()
        buffer.close()

        await message.answer_document(
            types.BufferedInputFile(pdf_data, filename=f"case_{case[0]}_report.pdf"),
            caption=f"📄 Отчёт по делу {case[0]}",
            reply_markup=get_back_button()
        )
        log_event(user_id, "export_pdf", case_number)
    except ImportError:
        await message.answer("⚠️ Функция экспорта PDF временно недоступна.", parse_mode="Markdown", reply_markup=get_back_button())

# ---------- ПОДПИСКА ----------
@dp.message(Command("subscribe"))
async def subscribe_command(message: types.Message):
    user_id = message.from_user.id
    active, trial_end, is_trial = check_subscription(user_id)

    if active and not is_trial:
        await message.answer("✅ У вас уже активна платная подписка!", parse_mode="Markdown", reply_markup=get_back_button())
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Купить подписку (500 Stars)", callback_data="buy_subscription")],
        [InlineKeyboardButton(text="🏠 Назад в меню", callback_data="back_to_menu")]
    ])

    await message.answer(
        f"💎 *Оформление подписки*\n\n"
        f"Стоимость: 500 Stars (≈500 руб)\n\n"
        f"Что вы получаете:\n"
        f"• ✅ Неограниченный мониторинг дел\n"
        f"• ✅ AI-аналитика и прогнозы\n"
        f"• ✅ Приоритетная поддержка\n"
        f"• ✅ Экспорт отчетов в PDF\n\n"
        f"Нажмите на кнопку ниже для оплаты через Telegram Stars:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@dp.callback_query(lambda c: c.data == "buy_subscription")
async def process_subscription_payment(callback: types.CallbackQuery):
    activate_subscription(callback.from_user.id, "demo_payment")

    await callback.message.edit_text(
        "✅ *Подписка активирована!*\n\n"
        "Спасибо за покупку! Теперь вам доступны все функции бота без ограничений.\n\n"
        "Используйте `/analytics` для просмотра статистики.",
        parse_mode="Markdown",
        reply_markup=get_back_button()
    )
    await callback.answer()
    log_event(callback.from_user.id, "subscribe")

# ---------- ПОМОЩЬ ----------
@dp.message(Command("help"))
async def help_command(message: types.Message):
    await message.answer(
        "📖 *Инструкция по использованию бота*\n\n"
        "*🏠 Навигация:*\n• `/start` — приветствие\n• `/menu` — главное меню\n• `/help` — эта инструкция\n\n"
        "*📚 Библиотека дел:*\n• `/library` — библиотека дел\n• `/add` — добавить дело\n• `/remove НОМЕР` — удалить дело\n• `/clear_all` — удалить все дела\n\n"
        "*🔄 Мониторинг:*\n• `/check` — проверить все дела\n• `/status НОМЕР` — проверить одно дело\n\n"
        "*📅 Сроки:*\n• `/deadline НОМЕР` — добавить срок\n• `/progress НОМЕР` — ход дела + AI-аналитика\n• `/complete ID` — отметить срок\n\n"
        "*🔔 Уведомления:*\n• `/notify_on` — включить\n• `/notify_off` — выключить\n\n"
        "*👤 Профиль:*\n• `/profile` — показать профиль\n• `/edit_profile` — заполнить/изменить\n• `/stats` — статистика\n\n"
        "*🤖 AI:*\n• `/insights` — AI-аналитика по всем делам\n\n"
        "*📊 Аналитика:*\n• `/analytics` — статистика использования\n\n"
        "*📄 Экспорт:*\n• `/export НОМЕР` — выгрузить отчёт по делу в PDF\n\n"
        "*💎 Подписка:*\n• `/subscribe` — оформить подписку\n\n"
        "*📧 Доступ:*\n• `/share НОМЕР EMAIL` — передать доступ клиенту",
        parse_mode="Markdown",
        reply_markup=get_back_button()
    )

# ---------- СТАНДАРТНЫЕ КОМАНДЫ УВЕДОМЛЕНИЙ ----------
@dp.message(Command("notify_on"))
async def notify_on_command(message: types.Message):
    mode = get_notification_settings(message.from_user.id)[1]
    set_notification_settings(message.from_user.id, True, mode)
    await message.answer("🔔 *Уведомления ВКЛЮЧЕНЫ*", parse_mode="Markdown", reply_markup=get_back_button())

@dp.message(Command("notify_off"))
async def notify_off_command(message: types.Message):
    set_notification_settings(message.from_user.id, False, 'silent')
    await message.answer("🔕 *Уведомления ВЫКЛЮЧЕНЫ*", parse_mode="Markdown", reply_markup=get_back_button())

# ---------- ОБРАБОТЧИК НЕИЗВЕСТНЫХ КОМАНД ----------
@dp.message()
async def unknown_command(message: types.Message):
    await message.answer("❌ Неизвестная команда.\n\nНажмите `/menu` для открытия главного меню или `/help` для списка команд.", parse_mode="Markdown", reply_markup=get_back_button())

print("✅ Все команды загружены")

# ================================================================
# ФОНОВАЯ ПРОВЕРКА
# ================================================================
async def background_check():
    print(f"[{datetime.now()}] 🔍 Запуск фоновой проверки...")
    all_users = get_all_users_cases()
    for user_id, cases in all_users.items():
        enabled, mode = get_notification_settings(user_id)
        if not enabled:
            continue
        for case_info in cases:
            if case_info['court_type'] == 'arbitrazh' and case_info['case_guid']:
                result = await parse_case_by_guid(case_info['case_guid'])
                if result.get('error'):
                    continue
                status_changed = result['status'] != case_info.get('last_status') if case_info.get('last_status') else True
                if status_changed:
                    if case_info.get('last_status') and case_info.get('last_check'):
                        try:
                            last_check = datetime.fromisoformat(case_info['last_check'])
                            days_in_status = (datetime.now() - last_check).days
                            save_status_change(user_id, case_info['case_number'], case_info['last_status'], result['status'], days_in_status)
                        except:
                            pass
                    update_case_status(user_id, case_info['case_number'], result['status'], result['next_hearing'], case_info['case_guid'])
                    if mode == 'loud' or (mode == 'silent' and "решение" in result['status'].lower()):
                        try:
                            await bot.send_message(
                                user_id,
                                f"🔄 *Изменение по делу*\n\n📌 Дело: `{case_info['case_number']}`\n📋 Новый статус: {result['status']}\n📅 Заседание: {result['next_hearing']}\n🔗 [Ссылка]({result['link']})",
                                parse_mode="Markdown",
                                disable_web_page_preview=True
                            )
                        except Exception as e:
                            print(f"Ошибка отправки: {e}")
        deadlines = get_deadlines_for_check(user_id)
        today = datetime.now().date()
        for deadline_id, case_number, name, date_str in deadlines:
            deadline_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            days_left = (deadline_date - today).days
            formatted_date = format_date_for_display(date_str)
            if days_left == 3:
                await bot.send_message(user_id, f"⚠️ *Напоминание о сроке!*\n\n📌 Дело: `{case_number}`\n📋 Срок: *{name}*\n📅 Осталось 3 дня до {formatted_date}", parse_mode="Markdown")
            elif days_left == 1:
                await bot.send_message(user_id, f"🔴 *Срочное напоминание!*\n\n📌 Дело: `{case_number}`\n📋 Срок: *{name}*\n📅 ЗАВТРА {formatted_date}", parse_mode="Markdown")
            elif days_left == 0:
                await bot.send_message(user_id, f"🔴 *СЕГОДНЯ последний день!*\n\n📌 Дело: `{case_number}`\n📋 Срок: *{name}*\n📅 {formatted_date} — сегодня!", parse_mode="Markdown")
        await asyncio.sleep(1)
    print(f"[{datetime.now()}] ✅ Фоновая проверка завершена")

# ================================================================
# ЗАПУСК БОТА
# ================================================================
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()
scheduler.add_job(background_check, 'interval', hours=6)
scheduler.start()
print("⏰ Планировщик запущен (проверка каждые 6 часов)")

async def main():
    print("🚀 ЗАПУСК БОТА")
    print("=" * 40)
    await init_cookies()
    try:
        me = await bot.get_me()
        print(f"✅ Бот запущен: @{me.username}")
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
