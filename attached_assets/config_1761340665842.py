# config.py
import os
from dotenv import load_dotenv

# Загружаем .env файл из директории, где находится config.py
env_path = os.path.join(os.path.dirname(__file__), '.env')
if not os.path.exists(env_path):
    print(f"Ошибка: Файл .env не найден по пути: {env_path}")
load_dotenv(dotenv_path=env_path)

# Проверяем загрузку токена
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TELEGRAM_BOT_TOKEN:
    print(f"Ошибка: TELEGRAM_BOT_TOKEN не найден в переменных окружения")
    print(f"Проверьте файл .env по пути: {env_path}")
else:
    print(f"✅ TELEGRAM_BOT_TOKEN успешно загружен")

# ИСПРАВЛЕНО: правильное получение ключей
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
BINANCE_SECRET_KEY = os.getenv('BINANCE_SECRET_KEY')

if not BINANCE_API_KEY or not BINANCE_SECRET_KEY:
    print("⚠️ ВНИМАНИЕ: Binance API ключи не найдены!")
else:
    print(f"✅ Binance API ключи загружены")

BINANCE_EXCHANGE = 'binance'
BINANCE_OPTIONS = {
    'defaultType': 'future',
    'apiKey': BINANCE_API_KEY,
    'secret': BINANCE_SECRET_KEY,
}

TIMEFRAMES = {
    '5m': '5m',
    '15m': '15m',
    '1h': '1h',
    '4h': '4h'
}

DEFAULT_TIMEFRAME = '5m'
DEFAULT_LOOKBACK = 100

ZONE_TOUCH_THRESHOLD = 3
ZONE_WIDTH_PERCENT = 0.5
APPROACH_DISTANCE_PERCENT = 2.0

CHECK_INTERVALS = {
    'continuous': 60,
    '5min': 300
}

DEFAULT_CHECK_INTERVAL = 'continuous'

CHART_STYLE = 'binance'
CHART_DPI = 100
CHART_FIGSIZE = (16, 9)