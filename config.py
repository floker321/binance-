import os

BINANCE_API_KEY = os.getenv('BINANCE_API_KEY', '')
BINANCE_SECRET_KEY = os.getenv('BINANCE_SECRET_KEY', '')

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
    '4h': '4h',
    '1d': '1d'
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
