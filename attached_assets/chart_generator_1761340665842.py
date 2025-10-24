# chart_generator.py
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd
from typing import List, Dict, Tuple, Optional
from config import *
import numpy as np
import logging
from PIL import Image
import io
import os

logger = logging.getLogger(__name__)

class ChartGenerator:
    def __init__(self):
        self.style = self._create_custom_style()
        self.max_width = 1920
        self.max_height = 1080
        self.max_file_size = 10 * 1024 * 1024
        Image.MAX_IMAGE_PIXELS = None

    def _create_custom_style(self):
        """Создаем стиль с черным фоном"""
        return mpf.make_mpf_style(
            base_mpf_style='nightclouds',
            rc={
                'figure.facecolor': '#000000',
                'axes.facecolor': '#000000',
                'axes.edgecolor': '#333333',
                'axes.labelcolor': '#CCCCCC',
                'xtick.color': '#CCCCCC',
                'ytick.color': '#CCCCCC',
                'grid.color': '#333333',
                'grid.alpha': 0.3,
                'font.size': 9,
            },
            marketcolors=mpf.make_marketcolors(
                up='#00FF00',    # Green for up candles
                down='#FF0000',  # Red for down candles
                edge='inherit',
                wick='inherit',
                volume='inherit',
            )
        )

    def _compress_image(self, input_path: str, output_path: str):
        try:
            if not os.path.exists(input_path):
                return None
            
            file_size = os.path.getsize(input_path)
            if file_size == 0:
                return None
            
            with Image.open(input_path) as img:
                if img.mode not in ('RGB', 'RGBA'):
                    img = img.convert('RGB')
                
                if img.width > self.max_width or img.height > self.max_height:
                    img.thumbnail((self.max_width, self.max_height), Image.Resampling.LANCZOS)
                
                if file_size <= self.max_file_size:
                    return input_path
                
                jpeg_path = output_path.replace('.png', '.jpg')
                quality = 95
                
                while quality >= 70:
                    buffer = io.BytesIO()
                    if img.mode == 'RGBA':
                        rgb_img = Image.new('RGB', img.size, (0, 0, 0))
                        rgb_img.paste(img, mask=img.split()[3])
                        rgb_img.save(buffer, format='JPEG', quality=quality, optimize=True)
                    else:
                        img.save(buffer, format='JPEG', quality=quality, optimize=True)
                    
                    if len(buffer.getvalue()) <= self.max_file_size:
                        with open(jpeg_path, 'wb') as f:
                            f.write(buffer.getvalue())
                        if jpeg_path != input_path and os.path.exists(input_path):
                            os.remove(input_path)
                        return jpeg_path
                    quality -= 5
                
                return input_path
        except Exception as e:
            logger.error(f"Ошибка сжатия: {e}")
            return input_path

    def generate_chart(self, df: pd.DataFrame, symbol: str, timeframe: str,
                       support_zones: List[Dict], resistance_zones: List[Dict], 
                       peaks: List[Tuple], troughs: List[Tuple], 
                       recent_peaks: List[Tuple], recent_troughs: List[Tuple],
                       current_price: Optional[float] = None, 
                       filename: str = 'chart.png') -> Optional[str]:
        
        if df is None or len(df) == 0:
            logger.error("Input DataFrame is empty or None")
            return None

        try:
            # Prepare and validate DataFrame
            df_chart = df.copy()
            df_chart['timestamp'] = pd.to_datetime(df_chart['timestamp'], unit='ms', errors='coerce')
            
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            for col in required_columns:
                if col not in df_chart.columns:
                    logger.warning(f"Column {col} missing, filling with placeholder values")
                    df_chart[col] = np.random.uniform(0.1, 0.15, len(df_chart))  # Placeholder

            df_chart = df_chart.dropna(subset=['timestamp'] + required_columns)
            if len(df_chart) == 0:
                logger.error("DataFrame has no valid data after cleaning")
                return None

            df_chart.set_index('timestamp', inplace=True)
            # Ensure the index is monotonic
            df_chart = df_chart.sort_index()

            # Rename columns to capitalized for mplfinance compatibility
            df_chart = df_chart.rename(columns={
                'open': 'Open',
                'high': 'High',
                'low': 'Low',
                'close': 'Close',
                'volume': 'Volume'
            })

            # Debug log
            logger.info(f"DataFrame columns: {df_chart.columns.tolist()}")
            logger.info(f"DataFrame shape: {df_chart.shape}")
            logger.info(f"Sample data: {df_chart.head().to_dict()}")

            # Prepare addplots for custom elements
            addplots = []
            fill_betweens = []

            # Подготовка для зон поддержки и сопротивления (используем hlines и fill_between)
            hlines_values = []
            hlines_colors = []
            zone_width = ZONE_WIDTH_PERCENT / 100  # Use config value for zone width

            # ЗОНЫ ПОДДЕРЖКИ
            if not support_zones:
                logger.warning("Support zones are empty")
            else:
                # Find the most recent trough to determine the start of zones
                latest_trough_time = max([ts for ts, _ in troughs], default=df_chart.index[-1])
                latest_trough_time = pd.to_datetime(latest_trough_time, unit='ms')
                
                for zone in support_zones[:3]:
                    if not isinstance(zone, dict) or not all(key in zone for key in ['price', 'min_price', 'max_price']):
                        logger.warning(f"Invalid support zone format: {zone}")
                        continue
                    try:
                        price = float(zone['price'])
                        min_price = float(zone['min_price'])
                        max_price = float(zone['max_price'])
                        # Enforce minimum band width if min_price equals max_price
                        if min_price == max_price:
                            min_price = price * (1 - zone_width / 2)
                            max_price = price * (1 + zone_width / 2)
                        hlines_values.append(price)
                        hlines_colors.append('#00D9A3')
                        # Draw zone only to the right of the latest trough
                        where = df_chart.index >= latest_trough_time
                        fill_betweens.append({
                            'y1': min_price,
                            'y2': max_price,
                            'color': '#00D9A3',
                            'alpha': 0.2,
                            'where': where
                        })
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Invalid support zone data: {zone}, error: {e}")
                        continue

            # ЗОНЫ СОПРОТИВЛЕНИЯ
            if not resistance_zones:
                logger.warning("Resistance zones are empty")
            else:
                # Find the most recent peak to determine the start of zones
                latest_peak_time = max([ts for ts, _ in peaks], default=df_chart.index[-1])
                latest_peak_time = pd.to_datetime(latest_peak_time, unit='ms')
                
                for zone in resistance_zones[:3]:
                    if not isinstance(zone, dict) or not all(key in zone for key in ['price', 'min_price', 'max_price']):
                        logger.warning(f"Invalid resistance zone format: {zone}")
                        continue
                    try:
                        price = float(zone['price'])
                        min_price = float(zone['min_price'])
                        max_price = float(zone['max_price'])
                        # Enforce minimum band width if min_price equals max_price
                        if min_price == max_price:
                            min_price = price * (1 - zone_width / 2)
                            max_price = price * (1 + zone_width / 2)
                        hlines_values.append(price)
                        hlines_colors.append('#EF5350')
                        # Draw zone only to the right of the latest peak
                        where = df_chart.index >= latest_peak_time
                        fill_betweens.append({
                            'y1': min_price,
                            'y2': max_price,
                            'color': '#EF5350',
                            'alpha': 0.2,
                            'where': where
                        })
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Invalid resistance zone data: {zone}, error: {e}")
                        continue
            
            # Формируем hlines в правильном формате для mplfinance
            hlines = None
            if hlines_values:
                hlines = dict(
                    hlines=hlines_values,
                    colors=hlines_colors,
                    linewidths=1.5,
                    alpha=0.6
                )

            # ПИКИ (scatter)
            if peaks:
                peaks_data = [(pd.to_datetime(ts, unit='ms'), price) for ts, price in peaks]
                peaks_df = pd.DataFrame(peaks_data, columns=['timestamp', 'price']).set_index('timestamp')
                peaks_series = peaks_df['price'].reindex(df_chart.index)
                addplots.append(mpf.make_addplot(peaks_series, type='scatter', markersize=150, marker='v', color='#FF1493', alpha=1.0))

            # ВПАДИНЫ (scatter)
            if troughs:
                troughs_data = [(pd.to_datetime(ts, unit='ms'), price) for ts, price in troughs]
                troughs_df = pd.DataFrame(troughs_data, columns=['timestamp', 'price']).set_index('timestamp')
                troughs_series = troughs_df['price'].reindex(df_chart.index)
                addplots.append(mpf.make_addplot(troughs_series, type='scatter', markersize=150, marker='^', color='#00D9A3', alpha=1.0))

            # ЛИНИИ ТРЕНДА
            if len(recent_peaks) >= 2:
                # Sort peaks by timestamp to ensure correct order
                sorted_peaks = sorted(recent_peaks[-2:], key=lambda x: x[0])
                peak_times = [pd.to_datetime(ts, unit='ms') for ts, _ in sorted_peaks]
                peak_prices = [price for _, price in sorted_peaks]
                # Create trend DataFrame starting from the earliest peak
                trend_df = pd.DataFrame({'price': peak_prices}, index=peak_times).sort_index()
                # Extend to the right edge of the chart
                last_time = df_chart.index[-1]
                if trend_df.index[-1] < last_time:
                    # Linearly interpolate price to the last timestamp
                    t1, t2 = trend_df.index[0], trend_df.index[-1]
                    p1, p2 = trend_df['price'].iloc[0], trend_df['price'].iloc[-1]
                    time_diff = (t2 - t1).total_seconds()
                    if time_diff > 0:
                        slope = (p2 - p1) / time_diff
                        time_to_last = (last_time - t1).total_seconds()
                        extended_price = p1 + slope * time_to_last
                        trend_df = trend_df._append(pd.DataFrame({'price': [extended_price]}, index=[last_time])).sort_index()
                # Reindex to match full df_chart index, filling with NaN before start
                trend_series = trend_df['price'].reindex(df_chart.index, method='ffill')
                if trend_series.notna().any():
                    addplots.append(mpf.make_addplot(trend_series, type='line', color='#EF5350', width=1.5, alpha=0.4))
                    # Add semi-transparent rectangle
                    y1 = trend_series * (1 - zone_width / 2)
                    y2 = trend_series * (1 + zone_width / 2)
                    where = trend_series.index >= trend_df.index[0]
                    fill_betweens.append({
                        'y1': y1.to_numpy(),  # Convert Series to NumPy array
                        'y2': y2.to_numpy(),  # Convert Series to NumPy array
                        'where': where,       # Already a NumPy array
                        'color': '#EF5350',
                        'alpha': 0.15
                    })

            if len(recent_troughs) >= 2:
                # Sort troughs by timestamp to ensure correct order
                sorted_troughs = sorted(recent_troughs[-2:], key=lambda x: x[0])
                trough_times = [pd.to_datetime(ts, unit='ms') for ts, _ in sorted_troughs]
                trough_prices = [price for _, price in sorted_troughs]
                # Create trend DataFrame starting from the earliest trough
                trend_df = pd.DataFrame({'price': trough_prices}, index=trough_times).sort_index()
                # Extend to the right edge of the chart
                last_time = df_chart.index[-1]
                if trend_df.index[-1] < last_time:
                    # Linearly interpolate price to the last timestamp
                    t1, t2 = trend_df.index[0], trend_df.index[-1]
                    p1, p2 = trend_df['price'].iloc[0], trend_df['price'].iloc[-1]
                    time_diff = (t2 - t1).total_seconds()
                    if time_diff > 0:
                        slope = (p2 - p1) / time_diff
                        time_to_last = (last_time - t1).total_seconds()
                        extended_price = p1 + slope * time_to_last
                        trend_df = trend_df._append(pd.DataFrame({'price': [extended_price]}, index=[last_time])).sort_index()
                # Reindex to match full df_chart index, filling with NaN before start
                trend_series = trend_df['price'].reindex(df_chart.index, method='ffill')
                if trend_series.notna().any():
                    addplots.append(mpf.make_addplot(trend_series, type='line', color='#00D9A3', width=1.5, alpha=0.4))
                    # Add semi-transparent rectangle
                    y1 = trend_series * (1 - zone_width / 2)
                    y2 = trend_series * (1 + zone_width / 2)
                    where = trend_series.index >= trend_df.index[0]
                    fill_betweens.append({
                        'y1': y1.to_numpy(),  # Convert Series to NumPy array
                        'y2': y2.to_numpy(),  # Convert Series to NumPy array
                        'where': where,       # Already a NumPy array
                        'color': '#00D9A3',
                        'alpha': 0.15
                    })

            # Заголовок
            price_range = df_chart['High'].max() - df_chart['Low'].min()
            natr = (price_range / df_chart['Close'].mean()) * 100 if df_chart['Close'].mean() != 0 else 0
            title = f"{symbol} - {timeframe.upper()} (NATR: {natr:.1f}%)"

            # Plot
            fig, axes = mpf.plot(
                df_chart,
                type='candle',
                style=self.style,
                volume=True,
                addplot=addplots,
                hlines=hlines,
                fill_between=fill_betweens,
                figsize=(16, 9),
                returnfig=True,
                title=title
            )

            # Сохранение
            fig.savefig(
                filename,
                dpi=100,
                bbox_inches='tight',
                facecolor='#000000',
                edgecolor='none',
                format='png',
                pad_inches=0.1
            )
            plt.close(fig)
            
            if not os.path.exists(filename):
                logger.error(f"Файл не создан: {filename}")
                return None
            
            logger.info(f"✅ График сохранен: {filename}")
            
            final_path = self._compress_image(filename, filename)
            return final_path if final_path and os.path.exists(final_path) else None

        except Exception as e:
            logger.error(f"❌ Ошибка генерации графика: {e}", exc_info=True)
            return None