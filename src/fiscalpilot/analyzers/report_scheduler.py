"""
Report Scheduler — automated report generation and delivery.

Provides:
- Scheduled report runs
- Multiple delivery channels (email, Slack, S3)
- Report templates
- Retry logic
- Run history
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable


class ReportFrequency(str, Enum):
    """How often to run reports."""
    
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    ON_DEMAND = "on_demand"


class DeliveryChannel(str, Enum):
    """Delivery channels for reports."""
    
    EMAIL = "email"
    SLACK = "slack"
    S3 = "s3"
    SFTP = "sftp"
    WEBHOOK = "webhook"


class ReportStatus(str, Enum):
    """Status of a scheduled report."""
    
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReportFormat(str, Enum):
    """Output format for reports."""
    
    PDF = "pdf"
    EXCEL = "excel"
    CSV = "csv"
    HTML = "html"
    MARKDOWN = "markdown"
    JSON = "json"


@dataclass
class DeliveryConfig:
    """Configuration for report delivery."""
    
    channel: DeliveryChannel
    
    # Email config
    email_to: list[str] = field(default_factory=list)
    email_cc: list[str] = field(default_factory=list)
    email_subject: str | None = None
    
    # Slack config
    slack_channel: str | None = None
    slack_webhook_url: str | None = None
    
    # S3 config
    s3_bucket: str | None = None
    s3_prefix: str | None = None
    
    # SFTP config
    sftp_host: str | None = None
    sftp_path: str | None = None
    sftp_username: str | None = None
    
    # Webhook config
    webhook_url: str | None = None
    webhook_headers: dict[str, str] = field(default_factory=dict)


@dataclass
class ScheduleConfig:
    """Configuration for report schedule."""
    
    frequency: ReportFrequency
    
    # Timing
    hour: int = 8  # Hour of day (0-23)
    minute: int = 0
    timezone: str = "UTC"
    
    # Days
    day_of_week: int | None = None  # 0=Monday, 6=Sunday (for weekly)
    day_of_month: int | None = None  # 1-31 (for monthly)
    
    # Business rules
    skip_weekends: bool = False
    skip_holidays: bool = False
    
    # Window
    start_date: datetime | None = None
    end_date: datetime | None = None


@dataclass
class ReportTemplate:
    """A report template."""
    
    id: str
    name: str
    description: str
    
    # Report type
    report_type: str  # e.g., "financial_summary", "kpi_dashboard", "custom"
    
    # Configuration
    parameters: dict[str, Any] = field(default_factory=dict)
    filters: dict[str, Any] = field(default_factory=dict)
    
    # Customization
    title: str | None = None
    logo_url: str | None = None
    custom_css: str | None = None
    
    # Sections to include
    sections: list[str] = field(default_factory=list)


@dataclass
class ScheduledReport:
    """A scheduled report configuration."""
    
    id: str
    name: str
    description: str
    
    # Template
    template_id: str
    template: ReportTemplate | None = None
    
    # Schedule
    schedule: ScheduleConfig = field(default_factory=lambda: ScheduleConfig(
        frequency=ReportFrequency.MONTHLY
    ))
    
    # Delivery
    format: ReportFormat = ReportFormat.PDF
    delivery: list[DeliveryConfig] = field(default_factory=list)
    
    # State
    is_enabled: bool = True
    last_run: datetime | None = None
    next_run: datetime | None = None
    
    # Owner
    owner_id: str | None = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class ReportRun:
    """A single run of a scheduled report."""
    
    id: str
    report_id: str
    report_name: str
    
    # Timing
    started_at: datetime
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    
    # Status
    status: ReportStatus = ReportStatus.SCHEDULED
    error_message: str | None = None
    retry_count: int = 0
    
    # Output
    output_format: ReportFormat = ReportFormat.PDF
    output_path: str | None = None
    output_size_bytes: int | None = None
    
    # Delivery
    delivery_results: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SchedulerStats:
    """Statistics about the scheduler."""
    
    total_reports: int = 0
    active_reports: int = 0
    
    runs_today: int = 0
    runs_this_week: int = 0
    runs_this_month: int = 0
    
    success_rate: float = 0.0
    avg_duration_seconds: float = 0.0
    
    upcoming_runs: list[tuple[str, datetime]] = field(default_factory=list)


class ReportScheduler:
    """Manage scheduled report generation and delivery.

    Usage::

        scheduler = ReportScheduler()
        
        # Create a template
        template = ReportTemplate(
            id="monthly_summary",
            name="Monthly Financial Summary",
            description="End of month financial overview",
            report_type="financial_summary",
            sections=["income_statement", "balance_sheet", "kpis"],
        )
        scheduler.add_template(template)
        
        # Schedule a report
        report = ScheduledReport(
            id="monthly_report_001",
            name="Monthly Report to CEO",
            description="Monthly financial summary",
            template_id="monthly_summary",
            schedule=ScheduleConfig(
                frequency=ReportFrequency.MONTHLY,
                day_of_month=1,
                hour=9,
            ),
            delivery=[
                DeliveryConfig(
                    channel=DeliveryChannel.EMAIL,
                    email_to=["ceo@company.com"],
                    email_subject="Monthly Financial Report",
                ),
            ],
        )
        scheduler.schedule_report(report)
        
        # Run pending reports
        scheduler.run_pending()
    """

    def __init__(self) -> None:
        self.templates: dict[str, ReportTemplate] = {}
        self.reports: dict[str, ScheduledReport] = {}
        self.runs: list[ReportRun] = []
        
        # Report generators
        self._generators: dict[str, Callable[[ReportTemplate, dict], bytes]] = {}
        
        # Delivery handlers
        self._delivery_handlers: dict[DeliveryChannel, Callable[[DeliveryConfig, bytes, str], bool]] = {}
        
        # Max retries
        self.max_retries = 3

    def add_template(self, template: ReportTemplate) -> None:
        """Add a report template."""
        self.templates[template.id] = template

    def get_template(self, template_id: str) -> ReportTemplate | None:
        """Get a template by ID."""
        return self.templates.get(template_id)

    def schedule_report(self, report: ScheduledReport) -> None:
        """Schedule a report."""
        # Link template
        if report.template_id and not report.template:
            report.template = self.templates.get(report.template_id)
        
        # Calculate next run
        report.next_run = self._calculate_next_run(report.schedule)
        
        self.reports[report.id] = report

    def unschedule_report(self, report_id: str) -> None:
        """Remove a scheduled report."""
        if report_id in self.reports:
            del self.reports[report_id]

    def enable_report(self, report_id: str) -> None:
        """Enable a report."""
        if report_id in self.reports:
            self.reports[report_id].is_enabled = True
            self.reports[report_id].next_run = self._calculate_next_run(
                self.reports[report_id].schedule
            )

    def disable_report(self, report_id: str) -> None:
        """Disable a report."""
        if report_id in self.reports:
            self.reports[report_id].is_enabled = False
            self.reports[report_id].next_run = None

    def register_generator(
        self,
        report_type: str,
        generator: Callable[[ReportTemplate, dict], bytes],
    ) -> None:
        """Register a report generator function.
        
        Args:
            report_type: The type of report.
            generator: Function that generates report content.
        """
        self._generators[report_type] = generator

    def register_delivery_handler(
        self,
        channel: DeliveryChannel,
        handler: Callable[[DeliveryConfig, bytes, str], bool],
    ) -> None:
        """Register a delivery handler.
        
        Args:
            channel: The delivery channel.
            handler: Function that delivers the report.
        """
        self._delivery_handlers[channel] = handler

    def _calculate_next_run(
        self,
        schedule: ScheduleConfig,
        from_date: datetime | None = None,
    ) -> datetime:
        """Calculate the next run time for a schedule."""
        now = from_date or datetime.now()
        
        # Start with today at scheduled time
        next_run = now.replace(
            hour=schedule.hour,
            minute=schedule.minute,
            second=0,
            microsecond=0,
        )
        
        # If already past today's time, move to tomorrow
        if next_run <= now:
            next_run += timedelta(days=1)
        
        if schedule.frequency == ReportFrequency.DAILY:
            pass  # Already set
        
        elif schedule.frequency == ReportFrequency.WEEKLY:
            target_dow = schedule.day_of_week or 0  # Monday default
            days_ahead = target_dow - next_run.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            next_run += timedelta(days=days_ahead)
        
        elif schedule.frequency == ReportFrequency.BIWEEKLY:
            target_dow = schedule.day_of_week or 0
            days_ahead = target_dow - next_run.weekday()
            if days_ahead <= 0:
                days_ahead += 14
            next_run += timedelta(days=days_ahead)
        
        elif schedule.frequency == ReportFrequency.MONTHLY:
            target_day = schedule.day_of_month or 1
            
            # Move to target day
            try:
                next_run = next_run.replace(day=target_day)
            except ValueError:
                # Day doesn't exist in month, use last day
                next_month = (next_run.month % 12) + 1
                next_year = next_run.year + (1 if next_month == 1 else 0)
                next_run = datetime(next_year, next_month, 1) - timedelta(days=1)
            
            # If past, move to next month
            if next_run <= now:
                month = next_run.month + 1
                year = next_run.year
                if month > 12:
                    month = 1
                    year += 1
                try:
                    next_run = next_run.replace(year=year, month=month, day=target_day)
                except ValueError:
                    # Handle months with fewer days
                    next_run = next_run.replace(year=year, month=month, day=28)
        
        elif schedule.frequency == ReportFrequency.QUARTERLY:
            # First day of next quarter
            current_quarter = (next_run.month - 1) // 3
            next_quarter_month = ((current_quarter + 1) % 4) * 3 + 1
            next_quarter_year = next_run.year + (1 if next_quarter_month == 1 else 0)
            next_run = datetime(
                next_quarter_year,
                next_quarter_month,
                schedule.day_of_month or 1,
                schedule.hour,
                schedule.minute,
            )
        
        elif schedule.frequency == ReportFrequency.YEARLY:
            next_run = datetime(
                next_run.year + 1,
                1,
                schedule.day_of_month or 1,
                schedule.hour,
                schedule.minute,
            )
        
        # Skip weekends if configured
        if schedule.skip_weekends:
            while next_run.weekday() >= 5:  # Saturday=5, Sunday=6
                next_run += timedelta(days=1)
        
        # Check schedule window
        if schedule.start_date and next_run < schedule.start_date:
            next_run = schedule.start_date
        
        if schedule.end_date and next_run > schedule.end_date:
            return None  # Schedule has ended
        
        return next_run

    def get_pending_reports(self) -> list[ScheduledReport]:
        """Get reports that are due to run."""
        now = datetime.now()
        pending = []
        
        for report in self.reports.values():
            if not report.is_enabled:
                continue
            if report.next_run and report.next_run <= now:
                pending.append(report)
        
        return sorted(pending, key=lambda r: r.next_run or now)

    def run_report(
        self,
        report_id: str,
        parameters: dict[str, Any] | None = None,
    ) -> ReportRun:
        """Run a single report immediately.
        
        Args:
            report_id: The report to run.
            parameters: Override parameters.
        
        Returns:
            The run result.
        """
        report = self.reports.get(report_id)
        if not report:
            raise ValueError(f"Report not found: {report_id}")
        
        run = ReportRun(
            id=f"run_{datetime.now().timestamp()}_{report_id}",
            report_id=report_id,
            report_name=report.name,
            started_at=datetime.now(),
            status=ReportStatus.RUNNING,
            output_format=report.format,
        )
        
        try:
            # Get template
            template = report.template or self.templates.get(report.template_id)
            if not template:
                raise ValueError(f"Template not found: {report.template_id}")
            
            # Generate report
            generator = self._generators.get(template.report_type)
            if not generator:
                raise ValueError(f"No generator for report type: {template.report_type}")
            
            merged_params = {**template.parameters, **(parameters or {})}
            content = generator(template, merged_params)
            
            run.output_size_bytes = len(content)
            
            # Deliver report
            for delivery_config in report.delivery:
                result = self._deliver(delivery_config, content, report)
                run.delivery_results.append(result)
            
            # Update status
            run.status = ReportStatus.COMPLETED
            run.completed_at = datetime.now()
            run.duration_seconds = (run.completed_at - run.started_at).total_seconds()
            
            # Update report state
            report.last_run = datetime.now()
            report.next_run = self._calculate_next_run(report.schedule)
        
        except Exception as e:
            run.status = ReportStatus.FAILED
            run.error_message = str(e)
            run.completed_at = datetime.now()
            run.duration_seconds = (run.completed_at - run.started_at).total_seconds()
        
        self.runs.append(run)
        return run

    def _deliver(
        self,
        config: DeliveryConfig,
        content: bytes,
        report: ScheduledReport,
    ) -> dict[str, Any]:
        """Deliver report via configured channel."""
        result = {
            "channel": config.channel.value,
            "success": False,
            "timestamp": datetime.now().isoformat(),
        }
        
        handler = self._delivery_handlers.get(config.channel)
        if not handler:
            result["error"] = f"No handler for channel: {config.channel.value}"
            return result
        
        try:
            filename = f"{report.name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.{report.format.value}"
            success = handler(config, content, filename)
            result["success"] = success
        except Exception as e:
            result["error"] = str(e)
        
        return result

    def run_pending(self) -> list[ReportRun]:
        """Run all pending reports."""
        pending = self.get_pending_reports()
        results = []
        
        for report in pending:
            run = self.run_report(report.id)
            results.append(run)
            
            # Retry failed reports
            if run.status == ReportStatus.FAILED and run.retry_count < self.max_retries:
                run.retry_count += 1
                retry_run = self.run_report(report.id)
                results.append(retry_run)
        
        return results

    def get_run_history(
        self,
        report_id: str | None = None,
        limit: int = 100,
    ) -> list[ReportRun]:
        """Get run history."""
        runs = self.runs
        
        if report_id:
            runs = [r for r in runs if r.report_id == report_id]
        
        return sorted(runs, key=lambda r: r.started_at, reverse=True)[:limit]

    def get_stats(self) -> SchedulerStats:
        """Get scheduler statistics."""
        now = datetime.now()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        
        runs_today = [r for r in self.runs if r.started_at >= today]
        runs_this_week = [r for r in self.runs if r.started_at >= week_ago]
        runs_this_month = [r for r in self.runs if r.started_at >= month_ago]
        
        completed = [r for r in self.runs if r.status == ReportStatus.COMPLETED]
        success_rate = len(completed) / len(self.runs) if self.runs else 0
        
        avg_duration = (
            sum(r.duration_seconds or 0 for r in completed) / len(completed)
            if completed else 0
        )
        
        # Upcoming runs
        upcoming = [
            (r.name, r.next_run)
            for r in self.reports.values()
            if r.is_enabled and r.next_run
        ]
        upcoming.sort(key=lambda x: x[1])
        
        return SchedulerStats(
            total_reports=len(self.reports),
            active_reports=sum(1 for r in self.reports.values() if r.is_enabled),
            runs_today=len(runs_today),
            runs_this_week=len(runs_this_week),
            runs_this_month=len(runs_this_month),
            success_rate=success_rate,
            avg_duration_seconds=avg_duration,
            upcoming_runs=upcoming[:10],
        )
