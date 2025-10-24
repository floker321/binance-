import json
import os
from typing import Dict, List, Set

class DataManager:
    def __init__(self, data_file='user_data.json'):
        self.data_file = data_file
        self.data = self._load_data()
    
    def _load_data(self) -> Dict:
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    # Мигрируем старые данные - добавляем sent_alerts если его нет
                    for user_id in data:
                        if 'sent_alerts' not in data[user_id]:
                            data[user_id]['sent_alerts'] = {}
                        if 'timeframes' not in data[user_id]:
                            data[user_id]['timeframes'] = ['5m', '15m', '1h', '4h', '1d']
                    return data
            except:
                return {}
        return {}
    
    def _save_data(self):
        with open(self.data_file, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def get_user_data(self, user_id: str) -> Dict:
        user_id = str(user_id)
        if user_id not in self.data:
            self.data[user_id] = {
                'tickers': [],
                'interval': 'continuous',
                'timeframes': ['5m', '15m', '1h', '4h', '1d'],
                'zones': {},
                'sent_alerts': {}
            }
            self._save_data()
        
        # Проверяем наличие sent_alerts у существующих пользователей
        if 'sent_alerts' not in self.data[user_id]:
            self.data[user_id]['sent_alerts'] = {}
            self._save_data()
        
        return self.data[user_id]
    
    def add_ticker(self, user_id: str, ticker: str) -> bool:
        user_data = self.get_user_data(user_id)
        ticker = ticker.upper()
        if ticker not in user_data['tickers']:
            user_data['tickers'].append(ticker)
            
            # Инициализируем zones если нет
            if 'zones' not in user_data:
                user_data['zones'] = {}
            user_data['zones'][ticker] = {}
            
            # Инициализируем sent_alerts если нет
            if 'sent_alerts' not in user_data:
                user_data['sent_alerts'] = {}
            user_data['sent_alerts'][ticker] = []
            
            self._save_data()
            return True
        return False
    
    def remove_ticker(self, user_id: str, ticker: str) -> bool:
        user_data = self.get_user_data(user_id)
        ticker = ticker.upper()
        if ticker in user_data['tickers']:
            user_data['tickers'].remove(ticker)
            if ticker in user_data.get('zones', {}):
                del user_data['zones'][ticker]
            if ticker in user_data.get('sent_alerts', {}):
                del user_data['sent_alerts'][ticker]
            self._save_data()
            return True
        return False
    
    def get_tickers(self, user_id: str) -> List[str]:
        return self.get_user_data(user_id)['tickers']
    
    def set_interval(self, user_id: str, interval: str):
        user_data = self.get_user_data(user_id)
        user_data['interval'] = interval
        self._save_data()
    
    def get_interval(self, user_id: str) -> str:
        return self.get_user_data(user_id)['interval']
    
    def get_timeframes(self, user_id: str) -> List[str]:
        return self.get_user_data(user_id)['timeframes']
    
    def update_zones(self, user_id: str, ticker: str, timeframe: str, support_zones: List, resistance_zones: List):
        user_data = self.get_user_data(user_id)
        ticker = ticker.upper()
        if 'zones' not in user_data:
            user_data['zones'] = {}
        if ticker not in user_data['zones']:
            user_data['zones'][ticker] = {}
        user_data['zones'][ticker][timeframe] = {
            'support': support_zones,
            'resistance': resistance_zones
        }
        self._save_data()
    
    def get_zones(self, user_id: str, ticker: str, timeframe: str) -> Dict:
        user_data = self.get_user_data(user_id)
        ticker = ticker.upper()
        return user_data.get('zones', {}).get(ticker, {}).get(timeframe, {'support': [], 'resistance': []})
    
    def is_alert_sent(self, user_id: str, ticker: str, zone_key: str) -> bool:
        """Проверяет был ли уже отправлен алерт для этой зоны"""
        user_data = self.get_user_data(user_id)
        ticker = ticker.upper()
        if 'sent_alerts' not in user_data:
            user_data['sent_alerts'] = {}
            self._save_data()
        if ticker not in user_data['sent_alerts']:
            user_data['sent_alerts'][ticker] = []
        return zone_key in user_data['sent_alerts'][ticker]
    
    def mark_alert_sent(self, user_id: str, ticker: str, zone_key: str):
        """Отмечает что алерт для зоны отправлен"""
        user_data = self.get_user_data(user_id)
        ticker = ticker.upper()
        if 'sent_alerts' not in user_data:
            user_data['sent_alerts'] = {}
        if ticker not in user_data['sent_alerts']:
            user_data['sent_alerts'][ticker] = []
        if zone_key not in user_data['sent_alerts'][ticker]:
            user_data['sent_alerts'][ticker].append(zone_key)
            self._save_data()
    
    def reset_alerts_for_ticker(self, user_id: str, ticker: str):
        """Сброс алертов для тикера (при пробитии зоны)"""
        user_data = self.get_user_data(user_id)
        ticker = ticker.upper()
        if 'sent_alerts' not in user_data:
            user_data['sent_alerts'] = {}
        if ticker in user_data['sent_alerts']:
            user_data['sent_alerts'][ticker] = []
            self._save_data()
    
    def get_all_users(self) -> List[str]:
        return list(self.data.keys())