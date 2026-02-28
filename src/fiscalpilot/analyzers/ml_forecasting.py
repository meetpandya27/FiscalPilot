"""
ML Forecasting Module — predictive analytics for financial data.

Provides:
- Time series forecasting
- Revenue prediction
- Expense forecasting
- Seasonal decomposition
- Trend detection
- Confidence intervals
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any


class ForecastModel(str, Enum):
    """Forecasting model types."""
    
    MOVING_AVERAGE = "moving_average"
    EXPONENTIAL_SMOOTHING = "exponential_smoothing"
    LINEAR_REGRESSION = "linear_regression"
    SEASONAL = "seasonal"
    ARIMA_LIKE = "arima_like"


class Seasonality(str, Enum):
    """Seasonality patterns."""
    
    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class TrendDirection(str, Enum):
    """Trend direction."""
    
    UP = "up"
    DOWN = "down"
    FLAT = "flat"
    VOLATILE = "volatile"


@dataclass
class DataPoint:
    """A time series data point."""
    
    timestamp: datetime
    value: float
    category: str | None = None
    is_actual: bool = True  # False for forecasted values


@dataclass
class SeasonalComponents:
    """Decomposed seasonal components."""
    
    trend: list[float]
    seasonal: list[float]
    residual: list[float]
    
    period: int  # e.g., 7 for weekly, 12 for monthly
    seasonality_strength: float  # 0-1


@dataclass
class ForecastPoint:
    """A forecasted value."""
    
    timestamp: datetime
    value: float
    
    # Confidence intervals
    lower_bound: float
    upper_bound: float
    confidence_level: float = 0.95
    
    # Components
    trend_component: float | None = None
    seasonal_component: float | None = None


@dataclass
class ForecastResult:
    """Result of a forecast."""
    
    # Model info
    model: ForecastModel
    created_at: datetime = field(default_factory=datetime.now)
    
    # Historical data used
    historical_start: datetime | None = None
    historical_end: datetime | None = None
    historical_points: int = 0
    
    # Forecast
    forecasts: list[ForecastPoint] = field(default_factory=list)
    
    # Accuracy metrics
    mape: float | None = None  # Mean Absolute Percentage Error
    rmse: float | None = None  # Root Mean Square Error
    mae: float | None = None  # Mean Absolute Error
    
    # Trend info
    trend_direction: TrendDirection = TrendDirection.FLAT
    trend_slope: float = 0.0
    
    # Seasonality
    seasonality: Seasonality = Seasonality.NONE
    seasonal_periods: list[int] = field(default_factory=list)


@dataclass
class AnomalyDetectionResult:
    """Result of anomaly detection."""
    
    timestamp: datetime
    value: float
    expected_value: float
    deviation: float
    z_score: float
    is_anomaly: bool
    direction: str  # "above" or "below"


class MLForecaster:
    """Machine learning-based forecasting.

    Usage::

        forecaster = MLForecaster()
        
        # Add historical data
        for date, value in historical_data:
            forecaster.add_data_point(date, value)
        
        # Generate forecast
        forecast = forecaster.forecast(
            periods=12,
            model=ForecastModel.EXPONENTIAL_SMOOTHING,
        )
        
        # Detect anomalies
        anomalies = forecaster.detect_anomalies()
    """

    def __init__(self) -> None:
        self.data: list[DataPoint] = []
        
        # Model parameters
        self.smoothing_factor = 0.3  # For exponential smoothing
        self.trend_factor = 0.1
        self.seasonal_factor = 0.1

    def add_data_point(
        self,
        timestamp: datetime,
        value: float,
        category: str | None = None,
    ) -> None:
        """Add a historical data point."""
        self.data.append(DataPoint(
            timestamp=timestamp,
            value=value,
            category=category,
            is_actual=True,
        ))
        # Keep sorted
        self.data.sort(key=lambda x: x.timestamp)

    def add_data_points(
        self,
        points: list[tuple[datetime, float]],
    ) -> None:
        """Add multiple data points."""
        for ts, val in points:
            self.add_data_point(ts, val)

    def _get_values(self, category: str | None = None) -> list[float]:
        """Get values as a list."""
        if category:
            return [p.value for p in self.data if p.category == category]
        return [p.value for p in self.data]

    def _moving_average(
        self,
        values: list[float],
        window: int = 3,
    ) -> list[float]:
        """Calculate moving average."""
        if len(values) < window:
            return values
        
        result = []
        for i in range(len(values)):
            if i < window - 1:
                result.append(values[i])
            else:
                avg = sum(values[i - window + 1:i + 1]) / window
                result.append(avg)
        
        return result

    def _exponential_smoothing(
        self,
        values: list[float],
        alpha: float = 0.3,
    ) -> list[float]:
        """Apply exponential smoothing."""
        if not values:
            return []
        
        result = [values[0]]
        for i in range(1, len(values)):
            smoothed = alpha * values[i] + (1 - alpha) * result[-1]
            result.append(smoothed)
        
        return result

    def _linear_regression(
        self,
        values: list[float],
    ) -> tuple[float, float]:
        """Calculate linear regression coefficients.
        
        Returns (slope, intercept).
        """
        n = len(values)
        if n < 2:
            return 0.0, values[0] if values else 0.0
        
        x = list(range(n))
        
        x_mean = sum(x) / n
        y_mean = sum(values) / n
        
        numerator = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return 0.0, y_mean
        
        slope = numerator / denominator
        intercept = y_mean - slope * x_mean
        
        return slope, intercept

    def _detect_seasonality(
        self,
        values: list[float],
    ) -> tuple[Seasonality, int]:
        """Detect seasonality in data.
        
        Returns (seasonality type, period).
        """
        if len(values) < 14:
            return Seasonality.NONE, 0
        
        # Check common periods
        periods_to_check = [7, 12, 30, 52, 365]
        best_period = 0
        best_autocorr = 0.0
        
        for period in periods_to_check:
            if len(values) < period * 2:
                continue
            
            # Calculate autocorrelation at this lag
            mean = sum(values) / len(values)
            variance = sum((v - mean) ** 2 for v in values) / len(values)
            
            if variance == 0:
                continue
            
            autocorr = 0.0
            for i in range(period, len(values)):
                autocorr += (values[i] - mean) * (values[i - period] - mean)
            autocorr /= (len(values) - period) * variance
            
            if autocorr > best_autocorr and autocorr > 0.5:
                best_autocorr = autocorr
                best_period = period
        
        if best_period == 0:
            return Seasonality.NONE, 0
        
        if best_period == 7:
            return Seasonality.WEEKLY, 7
        elif best_period == 12:
            return Seasonality.MONTHLY, 12
        elif best_period == 30:
            return Seasonality.MONTHLY, 30
        elif best_period == 52:
            return Seasonality.YEARLY, 52
        else:
            return Seasonality.YEARLY, best_period

    def _decompose_seasonal(
        self,
        values: list[float],
        period: int,
    ) -> SeasonalComponents:
        """Decompose time series into trend, seasonal, residual."""
        if len(values) < period * 2:
            return SeasonalComponents(
                trend=values,
                seasonal=[0.0] * len(values),
                residual=[0.0] * len(values),
                period=period,
                seasonality_strength=0.0,
            )
        
        # Calculate trend using centered moving average
        trend = self._moving_average(values, period)
        
        # Calculate seasonal component
        detrended = [values[i] - trend[i] for i in range(len(values))]
        
        # Average seasonal factors for each position in the period
        seasonal = []
        for i in range(len(values)):
            pos = i % period
            factors = [detrended[j] for j in range(pos, len(detrended), period)]
            if factors:
                seasonal.append(sum(factors) / len(factors))
            else:
                seasonal.append(0.0)
        
        # Calculate residual
        residual = [
            values[i] - trend[i] - seasonal[i]
            for i in range(len(values))
        ]
        
        # Calculate seasonality strength
        var_residual = statistics.variance(residual) if len(residual) > 1 else 0
        var_detrended = statistics.variance(detrended) if len(detrended) > 1 else 1
        seasonality_strength = max(0, 1 - var_residual / var_detrended) if var_detrended > 0 else 0
        
        return SeasonalComponents(
            trend=trend,
            seasonal=seasonal,
            residual=residual,
            period=period,
            seasonality_strength=seasonality_strength,
        )

    def _get_trend_direction(
        self,
        slope: float,
        values: list[float],
    ) -> TrendDirection:
        """Determine trend direction from slope and values."""
        if not values:
            return TrendDirection.FLAT
        
        avg = sum(values) / len(values)
        if avg == 0:
            return TrendDirection.FLAT
        
        # Normalize slope by average
        relative_slope = slope / avg
        
        # Check volatility
        if len(values) > 1:
            std = statistics.stdev(values)
            cv = std / avg if avg > 0 else 0  # Coefficient of variation
            
            if cv > 0.5:
                return TrendDirection.VOLATILE
        
        if relative_slope > 0.05:
            return TrendDirection.UP
        elif relative_slope < -0.05:
            return TrendDirection.DOWN
        else:
            return TrendDirection.FLAT

    def forecast(
        self,
        periods: int = 12,
        model: ForecastModel = ForecastModel.EXPONENTIAL_SMOOTHING,
        confidence_level: float = 0.95,
        category: str | None = None,
    ) -> ForecastResult:
        """Generate a forecast.
        
        Args:
            periods: Number of periods to forecast.
            model: Model type to use.
            confidence_level: Confidence level for intervals.
            category: Category to filter by.
        
        Returns:
            Forecast result with predictions.
        """
        values = self._get_values(category)
        
        if len(values) < 2:
            raise ValueError("Need at least 2 data points to forecast")
        
        # Determine time interval
        if len(self.data) >= 2:
            avg_interval = (
                (self.data[-1].timestamp - self.data[0].timestamp) /
                (len(self.data) - 1)
            )
        else:
            avg_interval = timedelta(days=1)
        
        last_timestamp = self.data[-1].timestamp if self.data else datetime.now()
        
        # Calculate base statistics
        mean = sum(values) / len(values)
        stdev = statistics.stdev(values) if len(values) > 1 else 0
        
        # Detect seasonality
        seasonality, period = self._detect_seasonality(values)
        
        # Get linear trend
        slope, intercept = self._linear_regression(values)
        trend_direction = self._get_trend_direction(slope, values)
        
        # Generate forecasts based on model
        forecasts = []
        
        if model == ForecastModel.MOVING_AVERAGE:
            smoothed = self._moving_average(values, window=min(7, len(values)))
            base_value = smoothed[-1] if smoothed else mean
            
            for i in range(periods):
                # Add slight trend
                predicted = base_value + slope * (len(values) + i)
                
                margin = 1.96 * stdev * math.sqrt(1 + (i + 1) / len(values))
                
                forecasts.append(ForecastPoint(
                    timestamp=last_timestamp + avg_interval * (i + 1),
                    value=predicted,
                    lower_bound=predicted - margin,
                    upper_bound=predicted + margin,
                    confidence_level=confidence_level,
                    trend_component=slope * (len(values) + i),
                ))
        
        elif model == ForecastModel.EXPONENTIAL_SMOOTHING:
            smoothed = self._exponential_smoothing(values, self.smoothing_factor)
            base_value = smoothed[-1] if smoothed else mean
            
            for i in range(periods):
                # Holt's method: level + trend
                predicted = base_value + slope * (i + 1)
                
                # Widen confidence interval over time
                margin = 1.96 * stdev * math.sqrt(1 + 0.1 * (i + 1))
                
                forecasts.append(ForecastPoint(
                    timestamp=last_timestamp + avg_interval * (i + 1),
                    value=predicted,
                    lower_bound=predicted - margin,
                    upper_bound=predicted + margin,
                    confidence_level=confidence_level,
                    trend_component=slope * (i + 1),
                ))
        
        elif model == ForecastModel.LINEAR_REGRESSION:
            for i in range(periods):
                x = len(values) + i
                predicted = intercept + slope * x
                
                # Prediction interval
                margin = 1.96 * stdev * math.sqrt(1 + 1/len(values) + (x - len(values)/2)**2 / sum((j - len(values)/2)**2 for j in range(len(values))))
                
                forecasts.append(ForecastPoint(
                    timestamp=last_timestamp + avg_interval * (i + 1),
                    value=predicted,
                    lower_bound=predicted - margin,
                    upper_bound=predicted + margin,
                    confidence_level=confidence_level,
                    trend_component=predicted - intercept,
                ))
        
        elif model == ForecastModel.SEASONAL:
            if period > 0:
                components = self._decompose_seasonal(values, period)
                
                # Extend trend
                trend_smoothed = self._exponential_smoothing(components.trend)
                trend_slope, trend_intercept = self._linear_regression(trend_smoothed)
                
                for i in range(periods):
                    trend_val = trend_intercept + trend_slope * (len(values) + i)
                    seasonal_val = components.seasonal[(len(values) + i) % period]
                    predicted = trend_val + seasonal_val
                    
                    residual_std = statistics.stdev(components.residual) if len(components.residual) > 1 else stdev
                    margin = 1.96 * residual_std * math.sqrt(1 + 0.05 * (i + 1))
                    
                    forecasts.append(ForecastPoint(
                        timestamp=last_timestamp + avg_interval * (i + 1),
                        value=predicted,
                        lower_bound=predicted - margin,
                        upper_bound=predicted + margin,
                        confidence_level=confidence_level,
                        trend_component=trend_val,
                        seasonal_component=seasonal_val,
                    ))
            else:
                # Fall back to exponential smoothing
                return self.forecast(periods, ForecastModel.EXPONENTIAL_SMOOTHING, confidence_level)
        
        elif model == ForecastModel.ARIMA_LIKE:
            # Simplified ARIMA-like model
            # Uses differencing and autoregressive component
            if len(values) >= 2:
                diffs = [values[i] - values[i-1] for i in range(1, len(values))]
                avg_diff = sum(diffs) / len(diffs)
            else:
                avg_diff = 0
            
            last_value = values[-1]
            
            for i in range(periods):
                # AR(1) component
                if i == 0:
                    predicted = last_value + avg_diff
                else:
                    predicted = forecasts[-1].value + avg_diff * (0.9 ** i)
                
                # Increasing uncertainty
                margin = 1.96 * stdev * math.sqrt(i + 1)
                
                forecasts.append(ForecastPoint(
                    timestamp=last_timestamp + avg_interval * (i + 1),
                    value=predicted,
                    lower_bound=predicted - margin,
                    upper_bound=predicted + margin,
                    confidence_level=confidence_level,
                    trend_component=avg_diff * (i + 1),
                ))
        
        # Calculate accuracy metrics on historical data
        mape, rmse, mae = self._calculate_accuracy(values, model)
        
        return ForecastResult(
            model=model,
            historical_start=self.data[0].timestamp if self.data else None,
            historical_end=self.data[-1].timestamp if self.data else None,
            historical_points=len(values),
            forecasts=forecasts,
            mape=mape,
            rmse=rmse,
            mae=mae,
            trend_direction=trend_direction,
            trend_slope=slope,
            seasonality=seasonality,
            seasonal_periods=[period] if period > 0 else [],
        )

    def _calculate_accuracy(
        self,
        values: list[float],
        model: ForecastModel,
    ) -> tuple[float | None, float | None, float | None]:
        """Calculate accuracy metrics using backtesting."""
        if len(values) < 4:
            return None, None, None
        
        # Use last 25% for validation
        split_idx = int(len(values) * 0.75)
        train = values[:split_idx]
        test = values[split_idx:]
        
        # Generate predictions for test period using model
        if model == ForecastModel.MOVING_AVERAGE:
            smoothed = self._moving_average(train)
            predictions = [smoothed[-1]] * len(test)
        elif model == ForecastModel.EXPONENTIAL_SMOOTHING:
            smoothed = self._exponential_smoothing(train)
            slope, _ = self._linear_regression(train)
            predictions = [smoothed[-1] + slope * (i + 1) for i in range(len(test))]
        elif model == ForecastModel.LINEAR_REGRESSION:
            slope, intercept = self._linear_regression(train)
            predictions = [intercept + slope * (split_idx + i) for i in range(len(test))]
        else:
            predictions = [train[-1]] * len(test)
        
        # Calculate MAPE
        ape_values = []
        for actual, pred in zip(test, predictions):
            if actual != 0:
                ape_values.append(abs((actual - pred) / actual) * 100)
        mape = sum(ape_values) / len(ape_values) if ape_values else None
        
        # Calculate RMSE
        se_values = [(actual - pred) ** 2 for actual, pred in zip(test, predictions)]
        rmse = math.sqrt(sum(se_values) / len(se_values)) if se_values else None
        
        # Calculate MAE
        ae_values = [abs(actual - pred) for actual, pred in zip(test, predictions)]
        mae = sum(ae_values) / len(ae_values) if ae_values else None
        
        return mape, rmse, mae

    def detect_anomalies(
        self,
        threshold_z_score: float = 2.5,
        category: str | None = None,
    ) -> list[AnomalyDetectionResult]:
        """Detect anomalies in the data.
        
        Args:
            threshold_z_score: Z-score threshold for anomaly detection.
            category: Category to filter by.
        
        Returns:
            List of detected anomalies.
        """
        values = self._get_values(category)
        
        if len(values) < 3:
            return []
        
        # Calculate expected values using exponential smoothing
        smoothed = self._exponential_smoothing(values)
        
        # Calculate residuals
        residuals = [values[i] - smoothed[i] for i in range(len(values))]
        
        mean_residual = sum(residuals) / len(residuals)
        std_residual = statistics.stdev(residuals) if len(residuals) > 1 else 1
        
        anomalies = []
        
        for i, point in enumerate(self.data):
            if category and point.category != category:
                continue
            
            if std_residual == 0:
                z_score = 0.0
            else:
                z_score = (residuals[i] - mean_residual) / std_residual
            
            is_anomaly = abs(z_score) > threshold_z_score
            
            if is_anomaly:
                anomalies.append(AnomalyDetectionResult(
                    timestamp=point.timestamp,
                    value=point.value,
                    expected_value=smoothed[i],
                    deviation=residuals[i],
                    z_score=z_score,
                    is_anomaly=True,
                    direction="above" if z_score > 0 else "below",
                ))
        
        return anomalies

    def predict_revenue(
        self,
        periods: int = 12,
        growth_rate: float | None = None,
    ) -> list[ForecastPoint]:
        """Specialized revenue prediction.
        
        Args:
            periods: Number of periods to forecast.
            growth_rate: Optional override growth rate.
        
        Returns:
            Revenue forecasts.
        """
        values = self._get_values()
        
        if not values:
            raise ValueError("No data points available")
        
        # If growth rate provided, use it
        if growth_rate is not None:
            monthly_rate = (1 + growth_rate) ** (1/12) - 1
            last_value = values[-1]
            
            forecasts = []
            last_ts = self.data[-1].timestamp
            interval = timedelta(days=30)
            
            for i in range(periods):
                predicted = last_value * ((1 + monthly_rate) ** (i + 1))
                stdev = statistics.stdev(values) if len(values) > 1 else predicted * 0.1
                
                forecasts.append(ForecastPoint(
                    timestamp=last_ts + interval * (i + 1),
                    value=predicted,
                    lower_bound=predicted - 1.96 * stdev,
                    upper_bound=predicted + 1.96 * stdev,
                ))
            
            return forecasts
        
        # Otherwise use best model
        result = self.forecast(periods, ForecastModel.EXPONENTIAL_SMOOTHING)
        return result.forecasts
