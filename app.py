import streamlit as st
import pandas as pd
import logging
from zone_analyzer import ZoneAnalyzer
from chart_generator import ChartGenerator
from config import TIMEFRAMES
import os
from datetime import datetime

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

def get_alert_status(current_price, zone, timeframe):
    zone_analyzer = get_zone_analyzer()
    alert_type, zone_key = zone_analyzer.check_price_alert(current_price, zone, timeframe)
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
    
    ticker_input = st.text_input(
        "Криптовалюта", 
        value="BTCUSDT",
        help="Введите тикер (например: BTCUSDT, ETHUSDT)"
    ).upper()
    
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
            
            if support_zones:
                st.markdown("### 🟢 Зоны поддержки")
                for i, zone in enumerate(support_zones[:3], 1):
                    alert_type = get_alert_status(current_price, zone, timeframe)
                    
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
                    alert_type = get_alert_status(current_price, zone, timeframe)
                    
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
