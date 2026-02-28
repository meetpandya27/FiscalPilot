"""
Audit Trail and Compliance Module — comprehensive change tracking.

Provides:
- Full change history for all records
- User action logging
- Data versioning
- Compliance reporting (SOX, SOC 2)
- Access logging
- Immutable audit log
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any


class AuditAction(str, Enum):
    """Types of auditable actions."""
    
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    VIEW = "view"
    EXPORT = "export"
    IMPORT = "import"
    APPROVE = "approve"
    REJECT = "reject"
    LOGIN = "login"
    LOGOUT = "logout"
    PERMISSION_CHANGE = "permission_change"
    SETTING_CHANGE = "setting_change"


class EntityType(str, Enum):
    """Types of auditable entities."""
    
    TRANSACTION = "transaction"
    INVOICE = "invoice"
    VENDOR = "vendor"
    ACCOUNT = "account"
    BUDGET = "budget"
    USER = "user"
    REPORT = "report"
    RULE = "rule"
    SETTING = "setting"
    INTEGRATION = "integration"


class ComplianceFramework(str, Enum):
    """Compliance frameworks."""
    
    SOX = "sox"
    SOC2 = "soc2"
    GAAP = "gaap"
    GDPR = "gdpr"
    PCI_DSS = "pci_dss"


@dataclass
class AuditEntry:
    """An immutable audit log entry."""
    
    id: str
    timestamp: datetime
    
    # Who
    user_id: str
    user_email: str
    
    # What
    action: AuditAction
    entity_type: EntityType
    entity_id: str
    
    # Optional fields
    user_ip: str | None = None
    user_agent: str | None = None
    entity_name: str | None = None
    
    # Changes
    old_values: dict[str, Any] | None = None
    new_values: dict[str, Any] | None = None
    changed_fields: list[str] = field(default_factory=list)
    
    # Context
    reason: str | None = None
    approval_id: str | None = None
    session_id: str | None = None
    
    # Integrity
    checksum: str = ""
    previous_checksum: str | None = None  # Chain to previous entry
    
    def __post_init__(self):
        """Calculate checksum after initialization."""
        if not self.checksum:
            self.checksum = self._calculate_checksum()
    
    def _calculate_checksum(self) -> str:
        """Calculate SHA-256 checksum of entry."""
        data = json.dumps({
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "action": self.action.value,
            "entity_type": self.entity_type.value,
            "entity_id": self.entity_id,
            "old_values": self.old_values,
            "new_values": self.new_values,
            "previous_checksum": self.previous_checksum,
        }, sort_keys=True, default=str)
        
        return hashlib.sha256(data.encode()).hexdigest()
    
    def verify_integrity(self) -> bool:
        """Verify entry has not been tampered with."""
        return self.checksum == self._calculate_checksum()


@dataclass
class DataVersion:
    """A versioned snapshot of an entity."""
    
    entity_type: EntityType
    entity_id: str
    version: int
    data: dict[str, Any]
    timestamp: datetime
    created_by: str
    audit_entry_id: str | None = None


@dataclass
class AccessLog:
    """Log of data access (views, exports)."""
    
    id: str
    timestamp: datetime
    user_id: str
    user_email: str
    
    action: str  # view, export, download
    resource_type: str
    resource_id: str | None = None
    
    # Details
    query: str | None = None
    record_count: int | None = None
    fields_accessed: list[str] = field(default_factory=list)
    
    # Context
    ip_address: str | None = None
    user_agent: str | None = None


@dataclass
class ComplianceReport:
    """Compliance audit report."""
    
    framework: ComplianceFramework
    report_date: datetime
    period_start: datetime
    period_end: datetime
    
    # Summary
    total_entries: int = 0
    entries_by_action: dict[str, int] = field(default_factory=dict)
    entries_by_entity: dict[str, int] = field(default_factory=dict)
    
    # Findings
    integrity_verified: bool = True
    chain_intact: bool = True
    anomalies: list[str] = field(default_factory=list)
    
    # Access review
    unique_users: int = 0
    privileged_actions: int = 0
    failed_access_attempts: int = 0
    
    # Recommendations
    findings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


class AuditTrail:
    """Manages audit logging and compliance.

    Usage::

        audit = AuditTrail()
        
        # Log an action
        audit.log(
            user_id="user123",
            user_email="john@example.com",
            action=AuditAction.UPDATE,
            entity_type=EntityType.TRANSACTION,
            entity_id="txn_456",
            old_values={"amount": "100.00"},
            new_values={"amount": "150.00"},
        )
        
        # Get audit history
        history = audit.get_entity_history(EntityType.TRANSACTION, "txn_456")
        
        # Generate compliance report
        report = audit.generate_compliance_report(ComplianceFramework.SOX)
    """

    def __init__(
        self,
        retention_days: int = 365 * 7,  # 7 years for SOX
    ) -> None:
        self.retention_days = retention_days
        
        self._entries: list[AuditEntry] = []
        self._versions: dict[str, list[DataVersion]] = {}  # entity_id -> versions
        self._access_logs: list[AccessLog] = []
        
        self._entry_counter = 0
        self._last_checksum: str | None = None

    def log(
        self,
        user_id: str,
        user_email: str,
        action: AuditAction,
        entity_type: EntityType,
        entity_id: str,
        entity_name: str | None = None,
        old_values: dict[str, Any] | None = None,
        new_values: dict[str, Any] | None = None,
        reason: str | None = None,
        user_ip: str | None = None,
        session_id: str | None = None,
    ) -> AuditEntry:
        """Log an auditable action.
        
        Args:
            user_id: ID of user performing action.
            user_email: Email of user.
            action: Type of action.
            entity_type: Type of entity being affected.
            entity_id: ID of entity.
            entity_name: Human-readable entity name.
            old_values: Previous values (for updates).
            new_values: New values.
            reason: Reason for the action.
            user_ip: User's IP address.
            session_id: Session identifier.
        
        Returns:
            The created audit entry.
        """
        self._entry_counter += 1
        
        # Determine changed fields
        changed_fields = []
        if old_values and new_values:
            all_keys = set(old_values.keys()) | set(new_values.keys())
            changed_fields = [
                k for k in all_keys
                if old_values.get(k) != new_values.get(k)
            ]
        
        entry = AuditEntry(
            id=f"audit_{self._entry_counter}_{datetime.now().timestamp()}",
            timestamp=datetime.now(),
            user_id=user_id,
            user_email=user_email,
            user_ip=user_ip,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            old_values=old_values,
            new_values=new_values,
            changed_fields=changed_fields,
            reason=reason,
            session_id=session_id,
            previous_checksum=self._last_checksum,
        )
        
        self._entries.append(entry)
        self._last_checksum = entry.checksum
        
        # Store version for data changes
        if action in (AuditAction.CREATE, AuditAction.UPDATE) and new_values:
            self._store_version(
                entity_type=entity_type,
                entity_id=entity_id,
                data=new_values,
                created_by=user_id,
                audit_entry_id=entry.id,
            )
        
        return entry

    def _store_version(
        self,
        entity_type: EntityType,
        entity_id: str,
        data: dict[str, Any],
        created_by: str,
        audit_entry_id: str | None = None,
    ) -> DataVersion:
        """Store a version of an entity."""
        key = f"{entity_type.value}:{entity_id}"
        
        if key not in self._versions:
            self._versions[key] = []
        
        version_num = len(self._versions[key]) + 1
        
        version = DataVersion(
            entity_type=entity_type,
            entity_id=entity_id,
            version=version_num,
            data=data.copy(),
            timestamp=datetime.now(),
            created_by=created_by,
            audit_entry_id=audit_entry_id,
        )
        
        self._versions[key].append(version)
        return version

    def log_access(
        self,
        user_id: str,
        user_email: str,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        query: str | None = None,
        record_count: int | None = None,
        fields_accessed: list[str] | None = None,
        ip_address: str | None = None,
    ) -> AccessLog:
        """Log data access (view, export, download)."""
        log = AccessLog(
            id=f"access_{datetime.now().timestamp()}",
            timestamp=datetime.now(),
            user_id=user_id,
            user_email=user_email,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            query=query,
            record_count=record_count,
            fields_accessed=fields_accessed or [],
            ip_address=ip_address,
        )
        
        self._access_logs.append(log)
        return log

    def get_entity_history(
        self,
        entity_type: EntityType,
        entity_id: str,
    ) -> list[AuditEntry]:
        """Get complete audit history for an entity."""
        return [
            e for e in self._entries
            if e.entity_type == entity_type and e.entity_id == entity_id
        ]

    def get_entity_versions(
        self,
        entity_type: EntityType,
        entity_id: str,
    ) -> list[DataVersion]:
        """Get all versions of an entity."""
        key = f"{entity_type.value}:{entity_id}"
        return self._versions.get(key, [])

    def get_version(
        self,
        entity_type: EntityType,
        entity_id: str,
        version: int,
    ) -> DataVersion | None:
        """Get a specific version of an entity."""
        versions = self.get_entity_versions(entity_type, entity_id)
        for v in versions:
            if v.version == version:
                return v
        return None

    def get_user_activity(
        self,
        user_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[AuditEntry]:
        """Get all activity by a user."""
        entries = [e for e in self._entries if e.user_id == user_id]
        
        if start_date:
            entries = [e for e in entries if e.timestamp >= start_date]
        if end_date:
            entries = [e for e in entries if e.timestamp <= end_date]
        
        return entries

    def search_entries(
        self,
        action: AuditAction | None = None,
        entity_type: EntityType | None = None,
        user_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        search_text: str | None = None,
    ) -> list[AuditEntry]:
        """Search audit entries with filters."""
        entries = self._entries.copy()
        
        if action:
            entries = [e for e in entries if e.action == action]
        if entity_type:
            entries = [e for e in entries if e.entity_type == entity_type]
        if user_id:
            entries = [e for e in entries if e.user_id == user_id]
        if start_date:
            entries = [e for e in entries if e.timestamp >= start_date]
        if end_date:
            entries = [e for e in entries if e.timestamp <= end_date]
        
        if search_text:
            search_lower = search_text.lower()
            def matches(e: AuditEntry) -> bool:
                if e.entity_name and search_lower in e.entity_name.lower():
                    return True
                if e.entity_id and search_lower in e.entity_id.lower():
                    return True
                if e.reason and search_lower in e.reason.lower():
                    return True
                return False
            entries = [e for e in entries if matches(e)]
        
        return entries

    def verify_chain_integrity(self) -> tuple[bool, list[str]]:
        """Verify the audit log chain integrity.
        
        Returns:
            Tuple of (is_valid, list of error messages).
        """
        errors = []
        
        if not self._entries:
            return True, []
        
        # First entry should have no previous checksum
        if self._entries[0].previous_checksum is not None:
            errors.append(f"Entry 0: unexpected previous checksum")
        
        # Verify each entry
        for i, entry in enumerate(self._entries):
            # Verify entry's own checksum
            if not entry.verify_integrity():
                errors.append(f"Entry {i}: checksum mismatch (possible tampering)")
            
            # Verify chain link
            if i > 0:
                expected_prev = self._entries[i - 1].checksum
                if entry.previous_checksum != expected_prev:
                    errors.append(f"Entry {i}: chain broken (previous checksum mismatch)")
        
        return len(errors) == 0, errors

    def generate_compliance_report(
        self,
        framework: ComplianceFramework,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> ComplianceReport:
        """Generate a compliance report for the specified framework.
        
        Args:
            framework: The compliance framework.
            start_date: Report period start.
            end_date: Report period end.
        
        Returns:
            Compliance report with findings.
        """
        end_date = end_date or datetime.now()
        start_date = start_date or datetime(2020, 1, 1)
        
        # Filter entries to period
        entries = [
            e for e in self._entries
            if start_date <= e.timestamp <= end_date
        ]
        
        # Calculate statistics
        entries_by_action: dict[str, int] = {}
        entries_by_entity: dict[str, int] = {}
        unique_users: set[str] = set()
        privileged_actions = 0
        
        privileged_action_types = {
            AuditAction.DELETE,
            AuditAction.PERMISSION_CHANGE,
            AuditAction.SETTING_CHANGE,
        }
        
        for entry in entries:
            # By action
            action_key = entry.action.value
            entries_by_action[action_key] = entries_by_action.get(action_key, 0) + 1
            
            # By entity
            entity_key = entry.entity_type.value
            entries_by_entity[entity_key] = entries_by_entity.get(entity_key, 0) + 1
            
            # Users
            unique_users.add(entry.user_id)
            
            # Privileged actions
            if entry.action in privileged_action_types:
                privileged_actions += 1
        
        # Verify integrity
        is_valid, integrity_errors = self.verify_chain_integrity()
        
        # Generate findings and recommendations based on framework
        findings = []
        recommendations = []
        anomalies = []
        
        if framework == ComplianceFramework.SOX:
            # SOX specific checks
            if entries_by_action.get("delete", 0) > entries_by_action.get("create", 0) * 0.1:
                findings.append("High delete-to-create ratio may indicate data manipulation")
            
            # Check for off-hours activity
            off_hours_count = sum(
                1 for e in entries
                if e.timestamp.hour < 6 or e.timestamp.hour > 22
            )
            if off_hours_count > len(entries) * 0.1:
                anomalies.append(f"{off_hours_count} entries during off-hours")
            
            recommendations.append("Review all privileged actions monthly")
            recommendations.append("Ensure segregation of duties for approval workflows")
        
        elif framework == ComplianceFramework.SOC2:
            # SOC 2 specific checks
            if not is_valid:
                findings.append("Audit log integrity compromised - investigate immediately")
            
            recommendations.append("Implement automated log backup and rotation")
            recommendations.append("Enable multi-factor authentication for all users")
        
        elif framework == ComplianceFramework.GDPR:
            # GDPR specific checks
            data_exports = entries_by_action.get("export", 0)
            if data_exports > 0:
                findings.append(f"{data_exports} data exports during period - verify legal basis")
            
            recommendations.append("Document legal basis for all data processing")
            recommendations.append("Implement data retention policy automation")
        
        if not is_valid:
            anomalies.extend(integrity_errors)
        
        return ComplianceReport(
            framework=framework,
            report_date=datetime.now(),
            period_start=start_date,
            period_end=end_date,
            total_entries=len(entries),
            entries_by_action=entries_by_action,
            entries_by_entity=entries_by_entity,
            integrity_verified=is_valid,
            chain_intact=is_valid,
            anomalies=anomalies,
            unique_users=len(unique_users),
            privileged_actions=privileged_actions,
            findings=findings,
            recommendations=recommendations,
        )

    def export_for_auditors(
        self,
        start_date: datetime,
        end_date: datetime,
        include_data: bool = False,
    ) -> dict[str, Any]:
        """Export audit data for external auditors.
        
        Args:
            start_date: Export period start.
            end_date: Export period end.
            include_data: Whether to include full data snapshots.
        
        Returns:
            Dict containing audit entries and metadata.
        """
        entries = [
            e for e in self._entries
            if start_date <= e.timestamp <= end_date
        ]
        
        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "total_entries": len(entries),
            "entries": [
                {
                    "id": e.id,
                    "timestamp": e.timestamp.isoformat(),
                    "user_id": e.user_id,
                    "user_email": e.user_email,
                    "action": e.action.value,
                    "entity_type": e.entity_type.value,
                    "entity_id": e.entity_id,
                    "entity_name": e.entity_name,
                    "changed_fields": e.changed_fields,
                    "reason": e.reason,
                    "checksum": e.checksum,
                }
                for e in entries
            ],
        }
        
        if include_data:
            export_data["data_versions"] = {}
            for key, versions in self._versions.items():
                period_versions = [
                    {
                        "version": v.version,
                        "timestamp": v.timestamp.isoformat(),
                        "created_by": v.created_by,
                        "data": v.data,
                    }
                    for v in versions
                    if start_date <= v.timestamp <= end_date
                ]
                if period_versions:
                    export_data["data_versions"][key] = period_versions
        
        return export_data
