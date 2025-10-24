import streamlit as st
import pandas as pd
import logging
from zone_analyzer import ZoneAnalyzer
from chart_generator import ChartGenerator
from config import TIMEFRAMES
import os
from datetime import datetime
from collections import deque
from database import (
    init_db, add_alert_to_db, get_alert_history,
    add_ticker_to_watchlist, remove_ticker_from_watchlist,
    get_watchlist, update_preferences, get_or_create_preferences
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Crypto Zone Alert System",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

if 'db_initialized' not in st.session_state:
    init_db()
    st.session_state.db_initialized = True

if 'alert_history' not in st.session_state:
    db_alerts = get_alert_history(limit=50)
    st.session_state.alert_history = deque([{
        'timestamp': alert.timestamp,
        'ticker': alert.ticker,
        'timeframe': alert.timeframe,
        'alert_type': alert.alert_type,
        'zone_type': alert.zone_type,
        'zone_price': alert.zone_price,
        'current_price': alert.current_price,
        'zone_touches': alert.zone_touches
    } for alert in db_alerts], maxlen=50)

if 'watchlist' not in st.session_state:
    db_watchlist = get_watchlist()
    st.session_state.watchlist = db_watchlist if db_watchlist else ['BTCUSDT']

if 'sent_alerts' not in st.session_state:
    st.session_state.sent_alerts = {}

st.markdown("""
    <style>
    .main {
        background-color: #0e1117;
    }
    .stAlert {
        background-color: #1e2127;
        border: 1px solid #333;
    }
    div[data-testid="stMetricValue"] {
        font-size: 24px;
    }
    </style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_zone_analyzer():
    return ZoneAnalyzer()

@st.cache_resource
def get_chart_generator():
    return ChartGenerator()

def get_alert_status(current_price, zone, timeframe, ticker):
    zone_analyzer = get_zone_analyzer()
    alert_type, zone_key = zone_analyzer.check_price_alert(current_price, zone, timeframe)
    
    if alert_type and zone_key:
        full_key = f"{ticker}_{zone_key}"
        
        if full_key not in st.session_state.sent_alerts:
            alert_record = {
                'timestamp': datetime.now(),
                'ticker': ticker,
                'timeframe': timeframe,
                'alert_type': alert_type,
                'zone_type': zone['type'],
                'zone_price': zone['price'],
                'current_price': current_price,
                'zone_touches': zone.get('touches', 0)
            }
            st.session_state.alert_history.appendleft(alert_record)
            st.session_state.sent_alerts[full_key] = True
            
            add_alert_to_db(alert_record)
            
            if alert_type == 'broken':
                keys_to_remove = [k for k in st.session_state.sent_alerts.keys() if k.startswith(f"{ticker}_")]
                for k in keys_to_remove:
                    del st.session_state.sent_alerts[k]
    
    return alert_type

def display_alert_badge(alert_type, zone_type):
    if alert_type == 'approaching':
        emoji = "🔔"
        color = "#FFA500"
        text = "ПРИБЛИЖЕНИЕ"
    elif alert_type == 'in_zone':
        emoji = "🎯"
        color = "#FFFF00"
        text = "В ЗОНЕ"
    elif alert_type == 'broken':
        emoji = "💥"
        color = "#FF0000"
        text = "ПРОБИТА"
    else:
        return None
    
    zone_color = "#00D9A3" if zone_type == "support" else "#EF5350"
    return f"""
    <div style='
        background: linear-gradient(90deg, {color}22 0%, {zone_color}22 100%);
        border-left: 4px solid {color};
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
    '>
        <span style='font-size: 20px;'>{emoji}</span>
        <strong style='color: {color}; font-size: 14px;'> {text}</strong>
        <span style='color: #CCCCCC; margin-left: 10px;'>
            {'🟢 Поддержка' if zone_type == 'support' else '🔴 Сопротивление'}
        </span>
    </div>
    """

st.title("📊 Crypto Zone Alert System")
st.markdown("Анализ зон поддержки и сопротивления с трёхуровневой системой алертов")

with st.sidebar:
    st.header("⚙️ Настройки")
    
    st.subheader("📋 Watchlist")
    new_ticker = st.text_input("Добавить тикер", placeholder="ETHUSDT", key="new_ticker_input")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("➕ Добавить", use_container_width=True):
            if new_ticker and new_ticker.upper() not in st.session_state.watchlist:
                st.session_state.watchlist.append(new_ticker.upper())
                add_ticker_to_watchlist(new_ticker.upper())
                st.rerun()
    with col2:
        if st.button("🗑️ Очистить все", use_container_width=True):
            for ticker in st.session_state.watchlist:
                remove_ticker_from_watchlist(ticker)
            st.session_state.watchlist = []
            st.rerun()
    
    if st.session_state.watchlist:
        selected_ticker = st.selectbox(
            "Выбрать из watchlist",
            options=st.session_state.watchlist,
            key="ticker_selector"
        )
        ticker_input = selected_ticker
        
        if st.button(f"❌ Удалить {selected_ticker}", use_container_width=True):
            st.session_state.watchlist.remove(selected_ticker)
            remove_ticker_from_watchlist(selected_ticker)
            st.rerun()
    else:
        ticker_input = st.text_input(
            "Криптовалюта", 
            value="BTCUSDT",
            help="Введите тикер (например: BTCUSDT, ETHUSDT)"
        ).upper()
    
    st.divider()
    
    timeframe = st.selectbox(
        "Таймфрейм",
        options=list(TIMEFRAMES.keys()),
        index=0,
        help="Выберите таймфрейм для анализа"
    )
    
    lookback = st.slider(
        "Количество свечей",
        min_value=50,
        max_value=500,
        value=200,
        step=50,
        help="Количество исторических свечей для анализа"
    )
    
    auto_refresh = st.checkbox("Автообновление", value=False)
    if auto_refresh:
        st.info("Обновление каждые 60 секунд")
        refresh_interval = 60
    
    analyze_button = st.button("🔍 Анализировать", use_container_width=True, type="primary")

if analyze_button or auto_refresh:
    with st.spinner(f"Загрузка данных {ticker_input} на {timeframe}..."):
        zone_analyzer = get_zone_analyzer()
        chart_generator = get_chart_generator()
        
        try:
            df = zone_analyzer.fetch_ohlcv(ticker_input, timeframe, lookback)
            
            if df is None or len(df) < 20:
                st.error(f"❌ Не удалось получить данные для {ticker_input} на {timeframe}")
                st.stop()
            
            current_price = zone_analyzer.get_current_price(ticker_input)
            
            if current_price is None:
                st.error("❌ Не удалось получить текущую цену")
                st.stop()
            
            support_zones, resistance_zones, peaks, troughs, recent_peaks, recent_troughs = \
                zone_analyzer.find_support_resistance_zones(df, timeframe)
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("💰 Текущая цена", f"${current_price:,.6f}")
            with col2:
                st.metric("🟢 Зоны поддержки", len(support_zones))
            with col3:
                st.metric("🔴 Зоны сопротивления", len(resistance_zones))
            with col4:
                st.metric("📈 Пики/Впадины", f"{len(peaks)}/{len(troughs)}")
            
            st.divider()
            
            chart_file = f"chart_{ticker_input}_{timeframe}_{datetime.now().timestamp()}.png"
            chart_path = chart_generator.generate_chart(
                df, ticker_input, timeframe, 
                support_zones, resistance_zones,
                peaks, troughs, recent_peaks, recent_troughs,
                current_price, chart_file
            )
            
            if chart_path and os.path.exists(chart_path):
                st.image(chart_path, use_container_width=True)
                try:
                    os.remove(chart_path)
                except:
                    pass
            else:
                st.error("❌ Не удалось создать график")
            
            st.divider()
            st.subheader("🚨 Статус алертов")
            
            alerts_found = False
            
            tabs = st.tabs(["🚨 Текущие алерты", "📜 История алертов"])
            
            with tabs[0]:
                if support_zones:
                    st.markdown("### 🟢 Зоны поддержки")
                    for i, zone in enumerate(support_zones[:3], 1):
                        alert_type = get_alert_status(current_price, zone, timeframe, ticker_input)
                        
                        col1, col2 = st.columns([3, 1])
                        
                        with col1:
                            st.markdown(f"**S{i}: ${zone['price']:,.6f}**")
                            st.caption(f"Диапазон: ${zone['min_price']:,.6f} - ${zone['max_price']:,.6f}")
                            st.caption(f"Касаний: {zone['touches']}")
                        
                        with col2:
                            if alert_type:
                                alert_html = display_alert_badge(alert_type, 'support')
                                if alert_html:
                                    st.markdown(alert_html, unsafe_allow_html=True)
                                    alerts_found = True
                            else:
                                st.info("Нет алерта")
                        
                        st.divider()
                
                if resistance_zones:
                    st.markdown("### 🔴 Зоны сопротивления")
                    for i, zone in enumerate(resistance_zones[:3], 1):
                        alert_type = get_alert_status(current_price, zone, timeframe, ticker_input)
                        
                        col1, col2 = st.columns([3, 1])
                        
                        with col1:
                            st.markdown(f"**R{i}: ${zone['price']:,.6f}**")
                            st.caption(f"Диапазон: ${zone['min_price']:,.6f} - ${zone['max_price']:,.6f}")
                            st.caption(f"Касаний: {zone['touches']}")
                        
                        with col2:
                            if alert_type:
                                alert_html = display_alert_badge(alert_type, 'resistance')
                                if alert_html:
                                    st.markdown(alert_html, unsafe_allow_html=True)
                                    alerts_found = True
                            else:
                                st.info("Нет алерта")
                        
                        st.divider()
            
            with tabs[1]:
                st.markdown("### 📜 История алертов")
                
                if st.session_state.alert_history:
                    filter_ticker = st.selectbox(
                        "Фильтр по тикеру",
                        options=['Все'] + list(set(alert['ticker'] for alert in st.session_state.alert_history)),
                        key="history_filter"
                    )
                    
                    filtered_alerts = st.session_state.alert_history
                    if filter_ticker != 'Все':
                        filtered_alerts = [a for a in st.session_state.alert_history if a['ticker'] == filter_ticker]
                    
                    for alert in filtered_alerts:
                        alert_type_map = {
                            'approaching': ('🔔', 'ПРИБЛИЖЕНИЕ', '#FFA500'),
                            'in_zone': ('🎯', 'В ЗОНЕ', '#FFFF00'),
                            'broken': ('💥', 'ПРОБИТА', '#FF0000')
                        }
                        emoji, text, color = alert_type_map.get(alert['alert_type'], ('❓', 'НЕИЗВЕСТНО', '#888'))
                        zone_emoji = '🟢' if alert['zone_type'] == 'support' else '🔴'
                        
                        st.markdown(f"""
                        <div style='background: #1e2127; border-left: 4px solid {color}; padding: 10px; border-radius: 5px; margin: 5px 0;'>
                            <div style='display: flex; justify-content: space-between; align-items: center;'>
                                <div>
                                    <span style='font-size: 18px;'>{emoji}</span>
                                    <strong style='color: {color};'> {text}</strong>
                                    <span style='margin-left: 10px;'>{zone_emoji} {alert['ticker']} - {alert['timeframe'].upper()}</span>
                                </div>
                                <span style='color: #888; font-size: 12px;'>{alert['timestamp'].strftime('%H:%M:%S')}</span>
                            </div>
                            <div style='margin-top: 5px; font-size: 13px; color: #CCC;'>
                                Зона: ${alert['zone_price']:,.6f} | Цена: ${alert['current_price']:,.6f} | Касаний: {alert['zone_touches']}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("История алертов пуста. Алерты будут появляться здесь по мере их возникновения.")
            
            if not alerts_found and (support_zones or resistance_zones):
                st.info("ℹ️ Нет активных алертов. Цена находится вне критических зон.")
            
            if not support_zones and not resistance_zones:
                st.warning("⚠️ Зоны не найдены. Попробуйте увеличить количество свечей.")
            
            st.divider()
            st.subheader("ℹ️ Информация о системе алертов")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("""
                    **🔔 ПРИБЛИЖЕНИЕ К ЗОНЕ**
                    - Цена в пределах 2% от зоны
                    - Подготовка к действию
                    - Следите за развитием
                """)
            
            with col2:
                st.markdown("""
                    **🎯 ВХОД В ЗОНУ**
                    - Цена внутри зоны
                    - Время для действия
                    - Возможен отскок или пробой
                """)
            
            with col3:
                st.markdown("""
                    **💥 ПРОБИТИЕ ЗОНЫ**
                    - Зона пробита
                    - Сильное движение
                    - Новый уровень поддержки/сопротивления
                """)
            
            if auto_refresh:
                import time
                time.sleep(refresh_interval)
                st.rerun()
                
        except Exception as e:
            st.error(f"❌ Ошибка: {str(e)}")
            logger.error(f"Ошибка анализа: {e}", exc_info=True)
else:
    st.info("👈 Выберите настройки на боковой панели и нажмите 'Анализировать'")
    
    st.markdown("""
    ### Добро пожаловать! 👋
    
    Эта система анализирует зоны поддержки и сопротивления на криптовалютном рынке
    и предоставляет трёхуровневую систему алертов:
    
    - **🔔 Приближение** - цена подходит к зоне (в пределах 2%)
    - **🎯 В зоне** - цена находится внутри зоны
    - **💥 Пробитие** - зона была пробита
    
    #### Как использовать:
    1. Введите тикер криптовалюты (например: BTCUSDT, ETHUSDT)
    2. Выберите таймфрейм (5m, 15m, 1h, 4h, 1d)
    3. Настройте количество свечей для анализа
    4. Нажмите "Анализировать"
    
    #### Что вы увидите:
    - 📊 График с визуализацией зон и трендовых линий
    - 🟢 Зоны поддержки (зелёные)
    - 🔴 Зоны сопротивления (красные)
    - 📈 Пики и впадины на графике
    - 🚨 Активные алерты для каждой зоны
    """)
