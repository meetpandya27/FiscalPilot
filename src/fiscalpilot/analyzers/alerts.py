"""
Proactive Alerts System — real-time monitoring and notifications.

Provides:
- Threshold-based alerts
- Trend-based alerts
- Anomaly detection alerts
- Budget variance alerts
- Cash flow alerts
- Compliance deadline alerts
- Custom alert rules
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Callable


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertType(str, Enum):
    """Types of alerts."""
    
    THRESHOLD = "threshold"
    TREND = "trend"
    ANOMALY = "anomaly"
    BUDGET = "budget"
    CASH_FLOW = "cash_flow"
    COMPLIANCE = "compliance"
    CUSTOM = "custom"


class AlertStatus(str, Enum):
    """Alert statuses."""
    
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SNOOZED = "snoozed"


class ComparisonOperator(str, Enum):
    """Comparison operators for rules."""
    
    GREATER_THAN = ">"
    GREATER_EQUAL = ">="
    LESS_THAN = "<"
    LESS_EQUAL = "<="
    EQUALS = "=="
    NOT_EQUALS = "!="
    BETWEEN = "between"


@dataclass
class AlertRule:
    """A rule that triggers alerts."""
    
    id: str
    name: str
    description: str
    alert_type: AlertType
    severity: AlertSeverity
    
    # Threshold rule settings
    metric: str | None = None
    operator: ComparisonOperator | None = None
    threshold: Decimal | None = None
    threshold_high: Decimal | None = None  # For BETWEEN
    
    # Trend rule settings
    trend_period_days: int | None = None
    trend_threshold_pct: float | None = None  # % change to trigger
    
    # Schedule
    check_frequency_minutes: int = 60
    active_hours_start: int | None = None  # Hour 0-23
    active_hours_end: int | None = None
    
    # Actions
    notify_email: list[str] = field(default_factory=list)
    notify_slack: str | None = None
    auto_escalate_after_minutes: int | None = None
    
    # State
    is_enabled: bool = True
    last_checked: datetime | None = None
    last_triggered: datetime | None = None


@dataclass
class Alert:
    """An alert instance."""
    
    id: str
    rule_id: str
    rule_name: str
    alert_type: AlertType
    severity: AlertSeverity
    status: AlertStatus
    
    # Content
    title: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    
    # Context
    metric_name: str | None = None
    metric_value: Any = None
    threshold: Any = None
    
    # Timestamps
    triggered_at: datetime = field(default_factory=datetime.now)
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    snoozed_until: datetime | None = None
    
    # Actions taken
    acknowledged_by: str | None = None
    resolution_notes: str | None = None
    
    @property
    def age_minutes(self) -> float:
        """Age of alert in minutes."""
        return (datetime.now() - self.triggered_at).total_seconds() / 60
    
    @property
    def is_overdue(self) -> bool:
        """Whether alert has been active too long."""
        # Consider overdue after 4 hours for critical, 24 hours otherwise
        max_age = 240 if self.severity == AlertSeverity.CRITICAL else 1440
        return self.age_minutes > max_age and self.status == AlertStatus.ACTIVE


@dataclass
class AlertSummary:
    """Summary of alerts."""
    
    total_active: int = 0
    total_acknowledged: int = 0
    total_resolved_today: int = 0
    
    by_severity: dict[str, int] = field(default_factory=dict)
    by_type: dict[str, int] = field(default_factory=dict)
    
    critical_alerts: list[Alert] = field(default_factory=list)
    overdue_alerts: list[Alert] = field(default_factory=list)


class AlertsManager:
    """Manage alerts and notifications.

    Usage::

        manager = AlertsManager()
        
        # Define rules
        manager.add_rule(AlertRule(
            id="cash_low",
            name="Low Cash Balance",
            description="Alert when cash drops below threshold",
            alert_type=AlertType.THRESHOLD,
            severity=AlertSeverity.CRITICAL,
            metric="cash_balance",
            operator=ComparisonOperator.LESS_THAN,
            threshold=Decimal("10000"),
        ))
        
        # Check metrics
        alerts = manager.check_metric("cash_balance", Decimal("8500"))
        
        # Manage alerts
        manager.acknowledge_alert(alert_id, acknowledged_by="user@example.com")
    """

    def __init__(self) -> None:
        self.rules: dict[str, AlertRule] = {}
        self.alerts: dict[str, Alert] = {}
        
        # Custom metric providers
        self._metric_providers: dict[str, Callable[[], Any]] = {}
        
        # Alert handlers
        self._handlers: list[Callable[[Alert], None]] = []
        
        # Historical values for trend detection
        self._metric_history: dict[str, list[tuple[datetime, Any]]] = {}

    def add_rule(self, rule: AlertRule) -> None:
        """Add an alert rule."""
        self.rules[rule.id] = rule

    def remove_rule(self, rule_id: str) -> None:
        """Remove an alert rule."""
        if rule_id in self.rules:
            del self.rules[rule_id]

    def enable_rule(self, rule_id: str) -> None:
        """Enable a rule."""
        if rule_id in self.rules:
            self.rules[rule_id].is_enabled = True

    def disable_rule(self, rule_id: str) -> None:
        """Disable a rule."""
        if rule_id in self.rules:
            self.rules[rule_id].is_enabled = False

    def register_metric_provider(
        self,
        metric: str,
        provider: Callable[[], Any],
    ) -> None:
        """Register a function that provides metric values."""
        self._metric_providers[metric] = provider

    def add_handler(self, handler: Callable[[Alert], None]) -> None:
        """Add an alert handler (callback when alert is created)."""
        self._handlers.append(handler)

    def _record_metric_value(self, metric: str, value: Any) -> None:
        """Record a metric value for trend analysis."""
        if metric not in self._metric_history:
            self._metric_history[metric] = []
        
        self._metric_history[metric].append((datetime.now(), value))
        
        # Keep only last 30 days
        cutoff = datetime.now() - timedelta(days=30)
        self._metric_history[metric] = [
            (ts, v) for ts, v in self._metric_history[metric]
            if ts > cutoff
        ]

    def _evaluate_threshold(
        self,
        value: Any,
        operator: ComparisonOperator,
        threshold: Decimal,
        threshold_high: Decimal | None = None,
    ) -> bool:
        """Evaluate if value triggers threshold."""
        try:
            val = Decimal(str(value))
        except (ValueError, TypeError):
            return False
        
        if operator == ComparisonOperator.GREATER_THAN:
            return val > threshold
        elif operator == ComparisonOperator.GREATER_EQUAL:
            return val >= threshold
        elif operator == ComparisonOperator.LESS_THAN:
            return val < threshold
        elif operator == ComparisonOperator.LESS_EQUAL:
            return val <= threshold
        elif operator == ComparisonOperator.EQUALS:
            return val == threshold
        elif operator == ComparisonOperator.NOT_EQUALS:
            return val != threshold
        elif operator == ComparisonOperator.BETWEEN:
            if threshold_high is None:
                return False
            return threshold <= val <= threshold_high
        
        return False

    def _evaluate_trend(
        self,
        metric: str,
        period_days: int,
        threshold_pct: float,
    ) -> tuple[bool, float]:
        """Evaluate if metric has trended beyond threshold.
        
        Returns (triggered, actual_change_pct).
        """
        history = self._metric_history.get(metric, [])
        if len(history) < 2:
            return False, 0.0
        
        cutoff = datetime.now() - timedelta(days=period_days)
        
        # Get values from start and end of period
        period_values = [(ts, v) for ts, v in history if ts > cutoff]
        if len(period_values) < 2:
            return False, 0.0
        
        start_value = period_values[0][1]
        end_value = period_values[-1][1]
        
        try:
            start_dec = Decimal(str(start_value))
            end_dec = Decimal(str(end_value))
            
            if start_dec == 0:
                return False, 0.0
            
            change_pct = float((end_dec - start_dec) / start_dec * 100)
            triggered = abs(change_pct) >= abs(threshold_pct)
            
            return triggered, change_pct
        except (ValueError, TypeError):
            return False, 0.0

    def _create_alert(
        self,
        rule: AlertRule,
        title: str,
        message: str,
        metric_value: Any = None,
        details: dict[str, Any] | None = None,
    ) -> Alert:
        """Create a new alert from a rule."""
        alert = Alert(
            id=f"alert_{datetime.now().timestamp()}_{rule.id}",
            rule_id=rule.id,
            rule_name=rule.name,
            alert_type=rule.alert_type,
            severity=rule.severity,
            status=AlertStatus.ACTIVE,
            title=title,
            message=message,
            metric_name=rule.metric,
            metric_value=metric_value,
            threshold=rule.threshold,
            details=details or {},
        )
        
        self.alerts[alert.id] = alert
        rule.last_triggered = datetime.now()
        
        # Call handlers
        for handler in self._handlers:
            try:
                handler(alert)
            except Exception:
                pass  # Don't let handler errors break alerting
        
        return alert

    def check_metric(
        self,
        metric: str,
        value: Any,
    ) -> list[Alert]:
        """Check a metric value against all relevant rules.
        
        Args:
            metric: Metric name.
            value: Current metric value.
        
        Returns:
            List of any alerts triggered.
        """
        # Record for trend analysis
        self._record_metric_value(metric, value)
        
        triggered_alerts = []
        
        for rule in self.rules.values():
            if not rule.is_enabled:
                continue
            if rule.metric != metric:
                continue
            
            # Check active hours
            if rule.active_hours_start is not None:
                current_hour = datetime.now().hour
                if not (rule.active_hours_start <= current_hour < (rule.active_hours_end or 24)):
                    continue
            
            # Check threshold rules
            if rule.alert_type == AlertType.THRESHOLD:
                if rule.operator and rule.threshold is not None:
                    if self._evaluate_threshold(
                        value,
                        rule.operator,
                        rule.threshold,
                        rule.threshold_high,
                    ):
                        alert = self._create_alert(
                            rule,
                            title=f"{rule.name} Alert",
                            message=f"{metric} is {value} (threshold: {rule.operator.value} {rule.threshold})",
                            metric_value=value,
                            details={
                                "metric": metric,
                                "value": str(value),
                                "threshold": str(rule.threshold),
                                "operator": rule.operator.value,
                            },
                        )
                        triggered_alerts.append(alert)
            
            # Check trend rules
            elif rule.alert_type == AlertType.TREND:
                if rule.trend_period_days and rule.trend_threshold_pct:
                    triggered, change_pct = self._evaluate_trend(
                        metric,
                        rule.trend_period_days,
                        rule.trend_threshold_pct,
                    )
                    if triggered:
                        direction = "increased" if change_pct > 0 else "decreased"
                        alert = self._create_alert(
                            rule,
                            title=f"{rule.name} Alert",
                            message=f"{metric} has {direction} {abs(change_pct):.1f}% over {rule.trend_period_days} days",
                            metric_value=value,
                            details={
                                "metric": metric,
                                "change_pct": change_pct,
                                "period_days": rule.trend_period_days,
                            },
                        )
                        triggered_alerts.append(alert)
            
            rule.last_checked = datetime.now()
        
        return triggered_alerts

    def check_all_metrics(self) -> list[Alert]:
        """Check all registered metric providers."""
        all_alerts = []
        
        for metric, provider in self._metric_providers.items():
            try:
                value = provider()
                alerts = self.check_metric(metric, value)
                all_alerts.extend(alerts)
            except Exception:
                pass  # Skip metrics that fail to evaluate
        
        return all_alerts

    def acknowledge_alert(
        self,
        alert_id: str,
        acknowledged_by: str,
        notes: str | None = None,
    ) -> Alert | None:
        """Acknowledge an alert."""
        alert = self.alerts.get(alert_id)
        if not alert:
            return None
        
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = datetime.now()
        alert.acknowledged_by = acknowledged_by
        if notes:
            alert.details["acknowledge_notes"] = notes
        
        return alert

    def resolve_alert(
        self,
        alert_id: str,
        resolution_notes: str | None = None,
    ) -> Alert | None:
        """Resolve an alert."""
        alert = self.alerts.get(alert_id)
        if not alert:
            return None
        
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.now()
        alert.resolution_notes = resolution_notes
        
        return alert

    def snooze_alert(
        self,
        alert_id: str,
        snooze_minutes: int = 60,
    ) -> Alert | None:
        """Snooze an alert for a period."""
        alert = self.alerts.get(alert_id)
        if not alert:
            return None
        
        alert.status = AlertStatus.SNOOZED
        alert.snoozed_until = datetime.now() + timedelta(minutes=snooze_minutes)
        
        return alert

    def get_active_alerts(
        self,
        severity: AlertSeverity | None = None,
        alert_type: AlertType | None = None,
    ) -> list[Alert]:
        """Get all active alerts with optional filters."""
        alerts = [
            a for a in self.alerts.values()
            if a.status in (AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED)
        ]
        
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        if alert_type:
            alerts = [a for a in alerts if a.alert_type == alert_type]
        
        # Check snoozed alerts
        now = datetime.now()
        for alert in alerts:
            if alert.status == AlertStatus.SNOOZED:
                if alert.snoozed_until and alert.snoozed_until <= now:
                    alert.status = AlertStatus.ACTIVE
        
        return sorted(alerts, key=lambda a: (a.severity.value, a.triggered_at))

    def get_alert_summary(self) -> AlertSummary:
        """Get summary of current alerts."""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        active = [a for a in self.alerts.values() if a.status == AlertStatus.ACTIVE]
        acknowledged = [a for a in self.alerts.values() if a.status == AlertStatus.ACKNOWLEDGED]
        resolved_today = [
            a for a in self.alerts.values()
            if a.status == AlertStatus.RESOLVED and a.resolved_at and a.resolved_at >= today
        ]
        
        by_severity: dict[str, int] = {}
        by_type: dict[str, int] = {}
        
        for alert in active + acknowledged:
            sev = alert.severity.value
            by_severity[sev] = by_severity.get(sev, 0) + 1
            
            typ = alert.alert_type.value
            by_type[typ] = by_type.get(typ, 0) + 1
        
        return AlertSummary(
            total_active=len(active),
            total_acknowledged=len(acknowledged),
            total_resolved_today=len(resolved_today),
            by_severity=by_severity,
            by_type=by_type,
            critical_alerts=[a for a in active if a.severity == AlertSeverity.CRITICAL],
            overdue_alerts=[a for a in active + acknowledged if a.is_overdue],
        )

    def create_budget_alert(
        self,
        budget_name: str,
        amount_used: Decimal,
        budget_total: Decimal,
        threshold_pct: float = 90.0,
    ) -> Alert | None:
        """Create an alert if budget usage exceeds threshold."""
        if budget_total <= 0:
            return None
        
        usage_pct = float(amount_used / budget_total * 100)
        
        if usage_pct >= threshold_pct:
            severity = AlertSeverity.CRITICAL if usage_pct >= 100 else AlertSeverity.HIGH
            
            alert = Alert(
                id=f"budget_alert_{datetime.now().timestamp()}",
                rule_id="budget_threshold",
                rule_name="Budget Alert",
                alert_type=AlertType.BUDGET,
                severity=severity,
                status=AlertStatus.ACTIVE,
                title=f"Budget Alert: {budget_name}",
                message=f"{budget_name} is at {usage_pct:.1f}% ({amount_used} / {budget_total})",
                metric_name=f"budget_{budget_name}",
                metric_value=usage_pct,
                threshold=threshold_pct,
                details={
                    "budget_name": budget_name,
                    "amount_used": float(amount_used),
                    "budget_total": float(budget_total),
                    "usage_pct": usage_pct,
                },
            )
            
            self.alerts[alert.id] = alert
            return alert
        
        return None

    def create_cash_flow_alert(
        self,
        days_until_zero: int | None,
        minimum_cash: Decimal,
        current_cash: Decimal,
    ) -> Alert | None:
        """Create alert for cash flow concerns."""
        alerts_created = []
        
        # Low cash alert
        if current_cash < minimum_cash:
            alert = Alert(
                id=f"cash_low_{datetime.now().timestamp()}",
                rule_id="cash_minimum",
                rule_name="Low Cash",
                alert_type=AlertType.CASH_FLOW,
                severity=AlertSeverity.CRITICAL,
                status=AlertStatus.ACTIVE,
                title="Low Cash Balance",
                message=f"Cash balance ({current_cash}) is below minimum ({minimum_cash})",
                metric_name="cash_balance",
                metric_value=float(current_cash),
                threshold=float(minimum_cash),
            )
            self.alerts[alert.id] = alert
            return alert
        
        # Runway alert
        if days_until_zero is not None and days_until_zero <= 30:
            severity = AlertSeverity.CRITICAL if days_until_zero <= 7 else AlertSeverity.HIGH
            
            alert = Alert(
                id=f"cash_runway_{datetime.now().timestamp()}",
                rule_id="cash_runway",
                rule_name="Cash Runway",
                alert_type=AlertType.CASH_FLOW,
                severity=severity,
                status=AlertStatus.ACTIVE,
                title="Cash Runway Warning",
                message=f"At current burn rate, cash will run out in {days_until_zero} days",
                metric_name="cash_runway_days",
                metric_value=days_until_zero,
                threshold=30,
            )
            self.alerts[alert.id] = alert
            return alert
        
        return None
