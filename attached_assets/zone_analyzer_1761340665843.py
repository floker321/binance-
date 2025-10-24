# zone_analyzer.py
import ccxt
import pandas as pd
import numpy as np
from scipy.signal import argrelextrema
from config import *
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ZoneAnalyzer:
    def __init__(self):
        self.exchange = ccxt.binance(BINANCE_OPTIONS)
        self.markets = None

    def _load_markets(self):
        if self.markets is None:
            try:
                self.markets = self.exchange.load_markets()
                logger.info(f"✅ Загружено {len(self.markets)} рынков")
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки рынков: {e}")
                self.markets = {}

    def normalize_symbol(self, symbol: str) -> str:
        """Нормализует символ для Binance Futures"""
        self._load_markets()
        symbol = symbol.upper().replace('/', '')
        
        # Для фьючерсов формат: BASE/USDT:USDT
        if symbol.endswith('USDT'):
            base = symbol[:-4]
            normalized = f"{base}/USDT:USDT"
            logger.info(f"🔄 Символ {symbol} -> {normalized}")
            return normalized
        
        return symbol

    def fetch_ohlcv(self, symbol: str, timeframe: str = '5m', limit: int = 200) -> pd.DataFrame:
        """Получает свечи для указанного таймфрейма"""
        try:
            symbol = self.normalize_symbol(symbol)
            logger.info(f"📊 Запрос данных: {symbol} {timeframe} (лимит: {limit})")
            
            # Получаем данные с биржи
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            
            if not ohlcv or len(ohlcv) == 0:
                logger.error(f"❌ Пустой ответ от биржи для {symbol} {timeframe}")
                return None
            
            logger.info(f"✅ Получено {len(ohlcv)} свечей")
            logger.info(f"Пример первой свечи: {ohlcv[0]}")
            logger.info(f"Пример последней свечи: {ohlcv[-1]}")
            
            # Создаем DataFrame
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # Проверяем типы данных
            logger.info(f"Типы данных ДО конвертации:\n{df.dtypes}")
            logger.info(f"Первая строка ДО:\n{df.iloc[0]}")
            
            # Конвертируем все в числа
            df['open'] = pd.to_numeric(df['open'], errors='coerce')
            df['high'] = pd.to_numeric(df['high'], errors='coerce')
            df['low'] = pd.to_numeric(df['low'], errors='coerce')
            df['close'] = pd.to_numeric(df['close'], errors='coerce')
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
            
            # timestamp оставляем как есть (в миллисекундах)
            df['timestamp'] = pd.to_numeric(df['timestamp'], errors='coerce')
            
            # Удаляем строки с NaN
            df = df.dropna()
            
            if len(df) == 0:
                logger.error(f"❌ Все данные стали NaN после конвертации")
                return None
            
            # Проверяем корректность данных
            if df['high'].min() <= 0 or df['low'].min() <= 0:
                logger.error(f"❌ Некорректные цены (<=0): high={df['high'].min()}, low={df['low'].min()}")
                return None
            
            # Проверяем логику OHLC
            invalid = df[(df['high'] < df['low']) | 
                        (df['high'] < df['open']) | 
                        (df['high'] < df['close']) |
                        (df['low'] > df['open']) | 
                        (df['low'] > df['close'])]
            
            if len(invalid) > 0:
                logger.warning(f"⚠️ Найдено {len(invalid)} некорректных свечей, удаляем их")
                df = df[~df.index.isin(invalid.index)]
            
            logger.info(f"✅ Итого корректных свечей: {len(df)}")
            logger.info(f"Диапазон цен: ${df['low'].min():.6f} - ${df['high'].max():.6f}")
            logger.info(f"Типы данных ПОСЛЕ:\n{df.dtypes}")
            
            return df
            
        except ccxt.NetworkError as e:
            logger.error(f"❌ Сетевая ошибка при получении данных {symbol}: {e}")
            return None
        except ccxt.ExchangeError as e:
            logger.error(f"❌ Ошибка биржи для {symbol}: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка OHLCV {symbol} {timeframe}: {e}", exc_info=True)
            return None

    def get_current_price(self, symbol: str) -> float:
        """Получает текущую цену"""
        try:
            symbol = self.normalize_symbol(symbol)
            ticker = self.exchange.fetch_ticker(symbol)
            price = ticker['last']
            logger.info(f"💰 Текущая цена {symbol}: ${price:.6f}")
            return price
        except Exception as e:
            logger.error(f"❌ Ошибка получения цены {symbol}: {e}")
            return None

    def _find_peaks_and_troughs(self, df: pd.DataFrame, order: int = 5):
        """Находит пики и впадины"""
        high = df['high'].values
        low = df['low'].values
        
        peaks_idx = argrelextrema(high, np.greater, order=order)[0]
        troughs_idx = argrelextrema(low, np.less, order=order)[0]
        
        peaks = [(df.iloc[i]['timestamp'], df.iloc[i]['high']) for i in peaks_idx]
        troughs = [(df.iloc[i]['timestamp'], df.iloc[i]['low']) for i in troughs_idx]
        
        logger.info(f"🔍 Найдено пиков: {len(peaks)}, впадин: {len(troughs)}")
        
        return peaks, troughs

    def _cluster_levels(self, levels, tolerance_percent=0.5):
        """Кластеризует уровни в зоны"""
        if not levels: 
            return []
        
        levels = sorted(levels)
        zones = []
        current = [levels[0]]
        
        for level in levels[1:]:
            center = np.mean(current)
            if abs(level - center) / center <= tolerance_percent / 100:
                current.append(level)
            else:
                zones.append({
                    'price': np.mean(current),
                    'touches': len(current),
                    'min_price': min(current),
                    'max_price': max(current)
                })
                current = [level]
        
        if current:
            zones.append({
                'price': np.mean(current),
                'touches': len(current),
                'min_price': min(current),
                'max_price': max(current)
            })
        
        return sorted(zones, key=lambda x: x['touches'], reverse=True)[:5]

    def find_support_resistance_zones(self, df: pd.DataFrame, timeframe: str):
        """Находит зоны поддержки/сопротивления"""
        peaks, troughs = self._find_peaks_and_troughs(df)
        
        resistance_levels = [p[1] for p in peaks]
        support_levels = [t[1] for t in troughs]
        
        resistance_zones = self._cluster_levels(resistance_levels, ZONE_WIDTH_PERCENT)
        support_zones = self._cluster_levels(support_levels, ZONE_WIDTH_PERCENT)
        
        recent_peaks = sorted(peaks, key=lambda x: x[0], reverse=True)[:2]
        recent_troughs = sorted(troughs, key=lambda x: x[0], reverse=True)[:2]

        current_price = df['close'].iloc[-1]
        
        # Фильтруем только непробитые зоны
        valid_support = []
        for zone in support_zones:
            if current_price >= zone['min_price']:
                z = zone.copy()
                z['type'] = 'support'
                z['timeframe'] = timeframe
                valid_support.append(z)
        
        valid_resistance = []
        for zone in resistance_zones:
            if current_price <= zone['max_price']:
                z = zone.copy()
                z['type'] = 'resistance'
                z['timeframe'] = timeframe
                valid_resistance.append(z)

        logger.info(f"✅ {timeframe}: Поддержка={len(valid_support)}, Сопротивление={len(valid_resistance)}")
        
        return valid_support, valid_resistance, peaks, troughs, recent_peaks, recent_troughs

    def check_price_alert(self, current_price: float, zone: dict, timeframe: str) -> tuple:
        """Проверяет нужен ли алерт"""
        price = zone['price']
        ztype = zone['type']
        width = ZONE_WIDTH_PERCENT / 100
        approach = APPROACH_DISTANCE_PERCENT / 100
        
        lower = price * (1 - width / 2)
        upper = price * (1 + width / 2)
        
        # ПРОБИТИЕ
        if ztype == 'support' and current_price < lower:
            return ('broken', f"{timeframe}_{ztype}_{price:.8f}")
        if ztype == 'resistance' and current_price > upper:
            return ('broken', f"{timeframe}_{ztype}_{price:.8f}")
        
        # В ЗОНЕ
        if lower <= current_price <= upper:
            return ('in_zone', f"{timeframe}_{ztype}_{price:.8f}")
        
        # ПРИБЛИЖЕНИЕ
        dist = abs(current_price - price) / price
        if dist <= approach:
            return ('approaching', f"{timeframe}_{ztype}_{price:.8f}")
        
        return (None, None)