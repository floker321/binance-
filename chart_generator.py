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
                up='#00FF00',
                down='#FF0000',
                edge='inherit',
                wick='inherit',
                volume='inherit',
            )
        )

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
            df_chart = df.copy()
            df_chart['timestamp'] = pd.to_datetime(df_chart['timestamp'], unit='ms', errors='coerce')
            
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            for col in required_columns:
                if col not in df_chart.columns:
                    logger.warning(f"Column {col} missing")
                    df_chart[col] = np.random.uniform(0.1, 0.15, len(df_chart))

            df_chart = df_chart.dropna(subset=['timestamp'] + required_columns)
            if len(df_chart) == 0:
                logger.error("DataFrame has no valid data after cleaning")
                return None

            df_chart.set_index('timestamp', inplace=True)
            df_chart = df_chart.sort_index()

            df_chart = df_chart.rename(columns={
                'open': 'Open',
                'high': 'High',
                'low': 'Low',
                'close': 'Close',
                'volume': 'Volume'
            })

            addplots = []
            fill_betweens = []

            hlines_values = []
            hlines_colors = []
            zone_width = ZONE_WIDTH_PERCENT / 100

            if support_zones:
                latest_trough_time = max([ts for ts, _ in troughs], default=df_chart.index[-1])
                latest_trough_time = pd.to_datetime(latest_trough_time, unit='ms')
                
                for zone in support_zones[:3]:
                    if not isinstance(zone, dict) or not all(key in zone for key in ['price', 'min_price', 'max_price']):
                        continue
                    try:
                        price = float(zone['price'])
                        min_price = float(zone['min_price'])
                        max_price = float(zone['max_price'])
                        if min_price == max_price:
                            min_price = price * (1 - zone_width / 2)
                            max_price = price * (1 + zone_width / 2)
                        hlines_values.append(price)
                        hlines_colors.append('#00D9A3')
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

            if resistance_zones:
                latest_peak_time = max([ts for ts, _ in peaks], default=df_chart.index[-1])
                latest_peak_time = pd.to_datetime(latest_peak_time, unit='ms')
                
                for zone in resistance_zones[:3]:
                    if not isinstance(zone, dict) or not all(key in zone for key in ['price', 'min_price', 'max_price']):
                        continue
                    try:
                        price = float(zone['price'])
                        min_price = float(zone['min_price'])
                        max_price = float(zone['max_price'])
                        if min_price == max_price:
                            min_price = price * (1 - zone_width / 2)
                            max_price = price * (1 + zone_width / 2)
                        hlines_values.append(price)
                        hlines_colors.append('#EF5350')
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
            
            hlines = None
            if hlines_values:
                hlines = dict(
                    hlines=hlines_values,
                    colors=hlines_colors,
                    linewidths=1.5,
                    alpha=0.6
                )

            if peaks:
                peaks_data = [(pd.to_datetime(ts, unit='ms'), price) for ts, price in peaks]
                peaks_df = pd.DataFrame(peaks_data, columns=['timestamp', 'price']).set_index('timestamp')
                peaks_series = peaks_df['price'].reindex(df_chart.index)
                addplots.append(mpf.make_addplot(peaks_series, type='scatter', markersize=150, marker='v', color='#FF1493', alpha=1.0))

            if troughs:
                troughs_data = [(pd.to_datetime(ts, unit='ms'), price) for ts, price in troughs]
                troughs_df = pd.DataFrame(troughs_data, columns=['timestamp', 'price']).set_index('timestamp')
                troughs_series = troughs_df['price'].reindex(df_chart.index)
                addplots.append(mpf.make_addplot(troughs_series, type='scatter', markersize=150, marker='^', color='#00D9A3', alpha=1.0))

            if len(recent_peaks) >= 2:
                sorted_peaks = sorted(recent_peaks[-2:], key=lambda x: x[0])
                peak_times = [pd.to_datetime(ts, unit='ms') for ts, _ in sorted_peaks]
                peak_prices = [price for _, price in sorted_peaks]
                trend_df = pd.DataFrame({'price': peak_prices}, index=peak_times).sort_index()
                last_time = df_chart.index[-1]
                if trend_df.index[-1] < last_time:
                    t1, t2 = trend_df.index[0], trend_df.index[-1]
                    p1, p2 = trend_df['price'].iloc[0], trend_df['price'].iloc[-1]
                    time_diff = (t2 - t1).total_seconds()
                    if time_diff > 0:
                        slope = (p2 - p1) / time_diff
                        time_to_last = (last_time - t1).total_seconds()
                        extended_price = p1 + slope * time_to_last
                        trend_df = pd.concat([trend_df, pd.DataFrame({'price': [extended_price]}, index=[last_time])]).sort_index()
                trend_series = trend_df['price'].reindex(df_chart.index, method='ffill')
                if trend_series.notna().any():
                    addplots.append(mpf.make_addplot(trend_series, type='line', color='#EF5350', width=1.5, alpha=0.4))

            if len(recent_troughs) >= 2:
                sorted_troughs = sorted(recent_troughs[-2:], key=lambda x: x[0])
                trough_times = [pd.to_datetime(ts, unit='ms') for ts, _ in sorted_troughs]
                trough_prices = [price for _, price in sorted_troughs]
                trend_df = pd.DataFrame({'price': trough_prices}, index=trough_times).sort_index()
                last_time = df_chart.index[-1]
                if trend_df.index[-1] < last_time:
                    t1, t2 = trend_df.index[0], trend_df.index[-1]
                    p1, p2 = trend_df['price'].iloc[0], trend_df['price'].iloc[-1]
                    time_diff = (t2 - t1).total_seconds()
                    if time_diff > 0:
                        slope = (p2 - p1) / time_diff
                        time_to_last = (last_time - t1).total_seconds()
                        extended_price = p1 + slope * time_to_last
                        trend_df = pd.concat([trend_df, pd.DataFrame({'price': [extended_price]}, index=[last_time])]).sort_index()
                trend_series = trend_df['price'].reindex(df_chart.index, method='ffill')
                if trend_series.notna().any():
                    addplots.append(mpf.make_addplot(trend_series, type='line', color='#00D9A3', width=1.5, alpha=0.4))

            price_range = df_chart['High'].max() - df_chart['Low'].min()
            natr = (price_range / df_chart['Close'].mean()) * 100 if df_chart['Close'].mean() != 0 else 0
            title = f"{symbol} - {timeframe.upper()} (NATR: {natr:.1f}%)"

            fig, axes = mpf.plot(
                df_chart,
                type='candle',
                style=self.style,
                volume=True,
                addplot=addplots if addplots else None,
                hlines=hlines,
                fill_between=fill_betweens if fill_betweens else None,
                figsize=(16, 9),
                returnfig=True,
                title=title
            )

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
            return filename

        except Exception as e:
            logger.error(f"❌ Ошибка генерации графика: {e}", exc_info=True)
            return None
