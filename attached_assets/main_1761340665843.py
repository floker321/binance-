# main.py
import asyncio
import logging
from typing import Optional
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
from config import *
from data_manager import DataManager
from zone_analyzer import ZoneAnalyzer
from chart_generator import ChartGenerator
import os

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

data_manager = DataManager()
zone_analyzer = ZoneAnalyzer()
chart_generator = ChartGenerator()

# Список всех таймфреймов для анализа
ALL_TIMEFRAMES = ['5m', '15m', '1h', '4h', '1d']

async def start(update: Update, context: CallbackContext):
    welcome_message = """
🤖 Zone Alert Bot - Мультитаймфреймный анализ

Команды:
/add BTCUSDT - добавить монету
/remove BTCUSDT - удалить
/list - список отслеживаемых
/interval [continuous/5min] - частота проверки
/status - текущие настройки
/chart BTCUSDT [5m/15m/1h/4h/1d] - график

📊 Анализирую все таймфреймы: 5m, 15m, 1h, 4h, 1d
✅ Каждая зона = 1 алерт (не повторяется)
"""
    await update.message.reply_text(welcome_message)

async def add_ticker(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    if not context.args:
        await update.message.reply_text("Укажите тикер: /add BTCUSDT")
        return
    
    ticker = context.args[0].upper()
    if data_manager.add_ticker(user_id, ticker):
        await update.message.reply_text(f"✅ {ticker} добавлен!\n🔄 Анализирую все таймфреймы...")
        
        # Анализируем все таймфреймы
        for tf in ALL_TIMEFRAMES:
            await analyze_timeframe(user_id, ticker, tf, update)
    else:
        await update.message.reply_text(f"⚠️ {ticker} уже отслеживается")

async def remove_ticker(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    if not context.args:
        await update.message.reply_text("Укажите тикер: /remove BTCUSDT")
        return
    
    ticker = context.args[0].upper()
    if data_manager.remove_ticker(user_id, ticker):
        await update.message.reply_text(f"✅ {ticker} удалён")
    else:
        await update.message.reply_text(f"⚠️ {ticker} не найден")

async def list_tickers(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    tickers = data_manager.get_tickers(user_id)
    if not tickers:
        await update.message.reply_text("Нет активных мониторингов.\n\nИспользуйте /add TICKER")
        return
    
    message = "📊 Активные мониторинги:\n\n" + "\n".join(f"• {t}" for t in tickers)
    message += f"\n\n⏱ Таймфреймы: {', '.join(ALL_TIMEFRAMES)}"
    await update.message.reply_text(message)

async def set_interval(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    if not context.args:
        await update.message.reply_text("Укажите: /interval continuous или /interval 5min")
        return
    
    interval = context.args[0].lower()
    if interval not in ['continuous', '5min']:
        await update.message.reply_text("Допустимо: continuous или 5min")
        return
    
    data_manager.set_interval(user_id, interval)
    freq_text = 'каждую минуту' if interval == 'continuous' else 'каждые 5 минут'
    await update.message.reply_text(f"✅ Частота проверки: {freq_text}")

async def status(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    user_data = data_manager.get_user_data(user_id)
    interval = "каждую минуту" if user_data['interval'] == "continuous" else "каждые 5 минут"
    
    message = f"""
📊 Ваши настройки:

⏱ Частота: {interval}
📈 Таймфреймы: {', '.join(ALL_TIMEFRAMES)}
💼 Мониторинг: {len(user_data['tickers'])} монет
"""
    await update.message.reply_text(message)

async def get_chart(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    if not context.args:
        await update.message.reply_text("Укажите тикер: /chart BTCUSDT [5m]")
        return
    
    ticker = context.args[0].upper()
    timeframe = context.args[1] if len(context.args) > 1 else '5m'
    
    if timeframe not in ALL_TIMEFRAMES:
        await update.message.reply_text(f"Доступны: {', '.join(ALL_TIMEFRAMES)}")
        return
    
    await update.message.reply_text(f"📊 Создаю график {ticker} на {timeframe}...")
    await analyze_timeframe(user_id, ticker, timeframe, update, force_chart=True)

async def analyze_timeframe(user_id: str, ticker: str, timeframe: str, 
                           update: Optional[Update] = None, force_chart: bool = False):
    """Анализирует один таймфрейм"""
    try:
        df = await asyncio.to_thread(zone_analyzer.fetch_ohlcv, ticker, timeframe, 200)
        
        if df is None or len(df) < 20:
            if force_chart and update:
                await update.message.reply_text(f"❌ Нет данных для {ticker} на {timeframe}")
            return
        
        support_zones, resistance_zones, peaks, troughs, recent_peaks, recent_troughs = \
            zone_analyzer.find_support_resistance_zones(df, timeframe)
        
        data_manager.update_zones(user_id, ticker, timeframe, support_zones, resistance_zones)
        current_price = await asyncio.to_thread(zone_analyzer.get_current_price, ticker)

        # Рисуем график если запрошен
        if force_chart and update:
            chart_file = f"chart_{user_id}_{ticker}_{timeframe}.png"
            chart_path = chart_generator.generate_chart(
                df, ticker, timeframe, support_zones, resistance_zones,
                peaks, troughs, recent_peaks, recent_troughs,
                current_price, chart_file
            )
            
            if chart_path and os.path.exists(chart_path):
                zones_info = f"📊 {ticker} - {timeframe.upper()}\n💰 ${current_price:.6f}\n\n"
                
                if support_zones:
                    zones_info += "🟢 Поддержка:\n"
                    for i, z in enumerate(support_zones[:3], 1):
                        zones_info += f"S{i}: ${z['price']:.6f} ({z['touches']} касаний)\n"
                
                if resistance_zones:
                    zones_info += "\n🔴 Сопротивление:\n"
                    for i, z in enumerate(resistance_zones[:3], 1):
                        zones_info += f"R{i}: ${z['price']:.6f} ({z['touches']} касаний)\n"
                
                with open(chart_path, 'rb') as f:
                    await update.message.reply_photo(f, caption=zones_info)
                os.remove(chart_path)
        
    except Exception as e:
        logger.error(f"Ошибка анализа {ticker} {timeframe}: {e}")
        if force_chart and update:
            await update.message.reply_text(f"❌ Ошибка: {e}")

async def check_alerts(context: CallbackContext):
    """Проверяет алерты по всем таймфреймам"""
    all_users = data_manager.get_all_users()
    
    for user_id in all_users:
        try:
            tickers = data_manager.get_tickers(user_id)
            
            for ticker in tickers:
                current_price = await asyncio.to_thread(zone_analyzer.get_current_price, ticker)
                if current_price is None:
                    continue
                
                # Проверяем все таймфреймы
                for timeframe in ALL_TIMEFRAMES:
                    zones = data_manager.get_zones(user_id, ticker, timeframe)
                    
                    # Проверяем зоны поддержки
                    for zone in zones.get('support', []):
                        alert_type, zone_key = zone_analyzer.check_price_alert(
                            current_price, zone, timeframe
                        )
                        
                        if alert_type and zone_key:
                            # Проверяем был ли уже алерт для этой зоны
                            if not data_manager.is_alert_sent(user_id, ticker, zone_key):
                                await send_alert(context, user_id, ticker, timeframe, 
                                               alert_type, zone, current_price)
                                # Отмечаем что алерт отправлен
                                data_manager.mark_alert_sent(user_id, ticker, zone_key)
                    
                    # Проверяем зоны сопротивления
                    for zone in zones.get('resistance', []):
                        alert_type, zone_key = zone_analyzer.check_price_alert(
                            current_price, zone, timeframe
                        )
                        
                        if alert_type and zone_key:
                            if not data_manager.is_alert_sent(user_id, ticker, zone_key):
                                await send_alert(context, user_id, ticker, timeframe,
                                               alert_type, zone, current_price)
                                data_manager.mark_alert_sent(user_id, ticker, zone_key)
                
        except Exception as e:
            logger.error(f"Ошибка проверки алертов для {user_id}: {e}")

async def send_alert(context: CallbackContext, user_id: str, ticker: str, 
                    timeframe: str, alert_type: str, zone: dict, current_price: float):
    """Отправляет алерт пользователю"""
    try:
        zone_type = "🟢 Поддержка" if zone['type'] == 'support' else "🔴 Сопротивление"
        zone_price = zone['price']
        
        if alert_type == 'approaching':
            emoji = "🔔"
            title = "ПРИБЛИЖЕНИЕ К ЗОНЕ"
            description = f"Цена приближается к зоне {zone_type.lower()}"
        elif alert_type == 'in_zone':
            emoji = "🎯"
            title = "ВХОД В ЗОНУ"
            description = f"Цена вошла в зону {zone_type.lower()}"
        elif alert_type == 'broken':
            emoji = "💥"
            title = "ПРОБИТИЕ ЗОНЫ"
            description = f"Зона {zone_type.lower()} пробита!"
            # При пробитии сбрасываем все алерты для перезапуска
            data_manager.reset_alerts_for_ticker(user_id, ticker)
        else:
            return
        
        message = f"""
{emoji} {title}

📊 {ticker} - {timeframe.upper()}
💰 Цена: ${current_price:.6f}
{zone_type}: ${zone_price:.6f}
💪 Касаний: {zone.get('touches', 0)}

{description}
"""
        
        await context.bot.send_message(chat_id=user_id, text=message)
        
        # Отправляем график
        df = await asyncio.to_thread(zone_analyzer.fetch_ohlcv, ticker, timeframe, 200)
        if df is not None:
            support_zones, resistance_zones, peaks, troughs, recent_peaks, recent_troughs = \
                zone_analyzer.find_support_resistance_zones(df, timeframe)
            
            chart_path = chart_generator.generate_chart(
                df, ticker, timeframe, support_zones, resistance_zones,
                peaks, troughs, recent_peaks, recent_troughs,
                current_price, f"alert_{user_id}_{ticker}_{timeframe}.png"
            )
            
            if chart_path and os.path.exists(chart_path):
                with open(chart_path, 'rb') as photo:
                    await context.bot.send_photo(chat_id=user_id, photo=photo)
                os.remove(chart_path)
        
        logger.info(f"✅ Алерт отправлен: {ticker} {timeframe} {alert_type} -> user {user_id}")
    
    except Exception as e:
        logger.error(f"Ошибка отправки алерта: {e}")

async def periodic_check(context: CallbackContext):
    """Периодическая проверка (каждую минуту)"""
    await check_alerts(context)

def main():
    if not TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN не найден в .env")
        return
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", add_ticker))
    application.add_handler(CommandHandler("remove", remove_ticker))
    application.add_handler(CommandHandler("list", list_tickers))
    application.add_handler(CommandHandler("interval", set_interval))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("chart", get_chart))
    
    job_queue = application.job_queue
    job_queue.run_repeating(periodic_check, interval=60, first=10)
    
    print("🤖 Бот запущен!")
    print(f"📊 Мультитаймфреймный анализ: {', '.join(ALL_TIMEFRAMES)}")
    print("✅ 1 зона = 1 алерт (без повторов)")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()