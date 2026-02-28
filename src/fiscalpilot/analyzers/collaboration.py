"""
Collaboration Module — comments, annotations, and team features.

Provides:
- Comments on transactions/invoices
- Mentions and notifications
- Activity feeds
- Task assignments
- Discussion threads
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class CommentType(str, Enum):
    """Type of comment."""
    
    COMMENT = "comment"
    QUESTION = "question"
    RESOLUTION = "resolution"
    APPROVAL = "approval"
    REJECTION = "rejection"
    NOTE = "note"


class NotificationType(str, Enum):
    """Type of notification."""
    
    MENTION = "mention"
    REPLY = "reply"
    ASSIGNMENT = "assignment"
    APPROVAL_REQUIRED = "approval_required"
    TASK_DUE = "task_due"
    COMMENT_ADDED = "comment_added"


class EntityType(str, Enum):
    """Entity types that can be commented on."""
    
    TRANSACTION = "transaction"
    INVOICE = "invoice"
    VENDOR = "vendor"
    REPORT = "report"
    BUDGET = "budget"
    FORECAST = "forecast"
    TASK = "task"


class TaskStatus(str, Enum):
    """Task status."""
    
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    """Task priority."""
    
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class User:
    """A system user."""
    
    id: str
    email: str
    name: str
    avatar_url: str | None = None
    role: str = "member"


@dataclass
class Mention:
    """A user mention in a comment."""
    
    user_id: str
    user_name: str
    start_index: int  # Position in comment text
    end_index: int


@dataclass
class Attachment:
    """An attachment on a comment."""
    
    id: str
    filename: str
    url: str
    size_bytes: int
    mime_type: str
    uploaded_by: str
    uploaded_at: datetime


@dataclass
class Comment:
    """A comment on an entity."""
    
    id: str
    entity_type: EntityType
    entity_id: str
    
    # Content
    text: str
    
    # Author
    author_id: str
    author_name: str
    
    # Type with default
    comment_type: CommentType = CommentType.COMMENT
    
    # Mentions
    mentions: list[Mention] = field(default_factory=list)
    
    # Attachments
    attachments: list[Attachment] = field(default_factory=list)
    
    # Threading
    parent_id: str | None = None  # For replies
    reply_count: int = 0
    
    # State
    is_edited: bool = False
    is_resolved: bool = False
    resolved_by: str | None = None
    resolved_at: datetime | None = None
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime | None = None

    @property
    def is_reply(self) -> bool:
        """Whether this is a reply to another comment."""
        return self.parent_id is not None


@dataclass
class Notification:
    """A notification for a user."""
    
    id: str
    user_id: str
    
    notification_type: NotificationType
    title: str
    message: str
    
    # Link to entity
    entity_type: EntityType | None = None
    entity_id: str | None = None
    comment_id: str | None = None
    
    # State
    is_read: bool = False
    read_at: datetime | None = None
    
    # Timestamp
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Task:
    """A task/to-do item."""
    
    id: str
    title: str
    description: str | None = None
    
    # Assignment
    assigned_to: str | None = None
    assigned_by: str | None = None
    assigned_at: datetime | None = None
    
    # Status
    status: TaskStatus = TaskStatus.OPEN
    priority: TaskPriority = TaskPriority.MEDIUM
    
    # Due date
    due_date: datetime | None = None
    
    # Link to entity
    entity_type: EntityType | None = None
    entity_id: str | None = None
    
    # Comments
    comment_count: int = 0
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    created_by: str | None = None

    @property
    def is_overdue(self) -> bool:
        """Whether task is past due."""
        if not self.due_date:
            return False
        if self.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            return False
        return datetime.now() > self.due_date


@dataclass
class ActivityItem:
    """An activity feed item."""
    
    id: str
    activity_type: str  # comment_added, task_created, status_changed, etc.
    description: str
    
    # Actor
    user_id: str
    user_name: str
    
    # Entity
    entity_type: EntityType
    entity_id: str
    entity_name: str | None = None
    
    # Timestamp
    timestamp: datetime = field(default_factory=datetime.now)


class CollaborationManager:
    """Manage comments, tasks, and team collaboration.

    Usage::

        collab = CollaborationManager()
        
        # Add a comment
        comment = collab.add_comment(
            entity_type=EntityType.INVOICE,
            entity_id="inv_001",
            text="@john Can you review this invoice?",
            author_id="user_123",
            author_name="Jane Doe",
        )
        
        # Create a task
        task = collab.create_task(
            title="Review Q4 invoices",
            assigned_to="user_456",
            due_date=datetime(2024, 1, 15),
        )
        
        # Get notifications
        notifications = collab.get_notifications("user_456")
    """

    def __init__(self) -> None:
        self.comments: dict[str, Comment] = {}
        self.notifications: dict[str, Notification] = {}
        self.tasks: dict[str, Task] = {}
        self.activities: list[ActivityItem] = []
        self.users: dict[str, User] = {}
        
        self._comment_counter = 0
        self._notification_counter = 0
        self._task_counter = 0
        self._activity_counter = 0

    def register_user(self, user: User) -> None:
        """Register a user."""
        self.users[user.id] = user

    def _parse_mentions(self, text: str) -> list[Mention]:
        """Parse @mentions from text."""
        mentions = []
        import re
        
        # Find @username patterns
        pattern = r'@(\w+)'
        for match in re.finditer(pattern, text):
            username = match.group(1)
            
            # Find user by name (case insensitive)
            user = None
            for u in self.users.values():
                if u.name.lower().replace(" ", "") == username.lower():
                    user = u
                    break
            
            if user:
                mentions.append(Mention(
                    user_id=user.id,
                    user_name=user.name,
                    start_index=match.start(),
                    end_index=match.end(),
                ))
        
        return mentions

    def _create_notification(
        self,
        user_id: str,
        notification_type: NotificationType,
        title: str,
        message: str,
        entity_type: EntityType | None = None,
        entity_id: str | None = None,
        comment_id: str | None = None,
    ) -> Notification:
        """Create and store a notification."""
        self._notification_counter += 1
        
        notification = Notification(
            id=f"notif_{self._notification_counter}",
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            message=message,
            entity_type=entity_type,
            entity_id=entity_id,
            comment_id=comment_id,
        )
        
        self.notifications[notification.id] = notification
        return notification

    def _add_activity(
        self,
        activity_type: str,
        description: str,
        user_id: str,
        user_name: str,
        entity_type: EntityType,
        entity_id: str,
        entity_name: str | None = None,
    ) -> ActivityItem:
        """Add an activity item."""
        self._activity_counter += 1
        
        activity = ActivityItem(
            id=f"activity_{self._activity_counter}",
            activity_type=activity_type,
            description=description,
            user_id=user_id,
            user_name=user_name,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
        )
        
        self.activities.append(activity)
        return activity

    def add_comment(
        self,
        entity_type: EntityType,
        entity_id: str,
        text: str,
        author_id: str,
        author_name: str,
        comment_type: CommentType = CommentType.COMMENT,
        parent_id: str | None = None,
    ) -> Comment:
        """Add a comment to an entity.
        
        Args:
            entity_type: Type of entity.
            entity_id: ID of entity.
            text: Comment text.
            author_id: ID of commenter.
            author_name: Name of commenter.
            comment_type: Type of comment.
            parent_id: Parent comment ID for replies.
        
        Returns:
            The created comment.
        """
        self._comment_counter += 1
        
        # Parse mentions
        mentions = self._parse_mentions(text)
        
        comment = Comment(
            id=f"comment_{self._comment_counter}",
            entity_type=entity_type,
            entity_id=entity_id,
            text=text,
            comment_type=comment_type,
            author_id=author_id,
            author_name=author_name,
            mentions=mentions,
            parent_id=parent_id,
        )
        
        self.comments[comment.id] = comment
        
        # Update parent reply count
        if parent_id and parent_id in self.comments:
            self.comments[parent_id].reply_count += 1
            
            # Notify parent author
            parent = self.comments[parent_id]
            if parent.author_id != author_id:
                self._create_notification(
                    user_id=parent.author_id,
                    notification_type=NotificationType.REPLY,
                    title="New reply to your comment",
                    message=f"{author_name} replied to your comment",
                    entity_type=entity_type,
                    entity_id=entity_id,
                    comment_id=comment.id,
                )
        
        # Create notifications for mentions
        for mention in mentions:
            if mention.user_id != author_id:
                self._create_notification(
                    user_id=mention.user_id,
                    notification_type=NotificationType.MENTION,
                    title="You were mentioned",
                    message=f"{author_name} mentioned you in a comment",
                    entity_type=entity_type,
                    entity_id=entity_id,
                    comment_id=comment.id,
                )
        
        # Add activity
        self._add_activity(
            activity_type="comment_added",
            description=f"{author_name} commented on {entity_type.value} {entity_id}",
            user_id=author_id,
            user_name=author_name,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        
        return comment

    def edit_comment(
        self,
        comment_id: str,
        new_text: str,
    ) -> Comment | None:
        """Edit a comment."""
        comment = self.comments.get(comment_id)
        if not comment:
            return None
        
        comment.text = new_text
        comment.is_edited = True
        comment.updated_at = datetime.now()
        comment.mentions = self._parse_mentions(new_text)
        
        return comment

    def delete_comment(self, comment_id: str) -> bool:
        """Delete a comment."""
        if comment_id in self.comments:
            del self.comments[comment_id]
            return True
        return False

    def resolve_comment(
        self,
        comment_id: str,
        resolved_by: str,
    ) -> Comment | None:
        """Mark a comment as resolved."""
        comment = self.comments.get(comment_id)
        if not comment:
            return None
        
        comment.is_resolved = True
        comment.resolved_by = resolved_by
        comment.resolved_at = datetime.now()
        
        return comment

    def get_comments(
        self,
        entity_type: EntityType,
        entity_id: str,
        include_resolved: bool = True,
    ) -> list[Comment]:
        """Get comments for an entity.
        
        Args:
            entity_type: Type of entity.
            entity_id: ID of entity.
            include_resolved: Include resolved comments.
        
        Returns:
            List of comments.
        """
        comments = [
            c for c in self.comments.values()
            if c.entity_type == entity_type and c.entity_id == entity_id
        ]
        
        if not include_resolved:
            comments = [c for c in comments if not c.is_resolved]
        
        # Sort by date, with replies after their parent
        root_comments = [c for c in comments if not c.parent_id]
        root_comments.sort(key=lambda c: c.created_at)
        
        result = []
        for root in root_comments:
            result.append(root)
            # Add replies
            replies = [c for c in comments if c.parent_id == root.id]
            replies.sort(key=lambda c: c.created_at)
            result.extend(replies)
        
        return result

    def create_task(
        self,
        title: str,
        description: str | None = None,
        assigned_to: str | None = None,
        assigned_by: str | None = None,
        due_date: datetime | None = None,
        priority: TaskPriority = TaskPriority.MEDIUM,
        entity_type: EntityType | None = None,
        entity_id: str | None = None,
        created_by: str | None = None,
    ) -> Task:
        """Create a task.
        
        Args:
            title: Task title.
            description: Task description.
            assigned_to: User ID to assign to.
            assigned_by: User ID assigning the task.
            due_date: Due date.
            priority: Priority level.
            entity_type: Related entity type.
            entity_id: Related entity ID.
            created_by: User ID creating the task.
        
        Returns:
            The created task.
        """
        self._task_counter += 1
        
        task = Task(
            id=f"task_{self._task_counter}",
            title=title,
            description=description,
            assigned_to=assigned_to,
            assigned_by=assigned_by,
            assigned_at=datetime.now() if assigned_to else None,
            due_date=due_date,
            priority=priority,
            entity_type=entity_type,
            entity_id=entity_id,
            created_by=created_by,
        )
        
        self.tasks[task.id] = task
        
        # Notify assignee
        if assigned_to:
            assigner = self.users.get(assigned_by) if assigned_by else None
            assigner_name = assigner.name if assigner else "Someone"
            
            self._create_notification(
                user_id=assigned_to,
                notification_type=NotificationType.ASSIGNMENT,
                title="New task assigned",
                message=f"{assigner_name} assigned you: {title}",
            )
        
        return task

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
    ) -> Task | None:
        """Update task status."""
        task = self.tasks.get(task_id)
        if not task:
            return None
        
        task.status = status
        if status == TaskStatus.COMPLETED:
            task.completed_at = datetime.now()
        
        return task

    def assign_task(
        self,
        task_id: str,
        user_id: str,
        assigned_by: str,
    ) -> Task | None:
        """Assign a task to a user."""
        task = self.tasks.get(task_id)
        if not task:
            return None
        
        task.assigned_to = user_id
        task.assigned_by = assigned_by
        task.assigned_at = datetime.now()
        
        # Notify
        assigner = self.users.get(assigned_by)
        self._create_notification(
            user_id=user_id,
            notification_type=NotificationType.ASSIGNMENT,
            title="Task assigned to you",
            message=f"{assigner.name if assigner else 'Someone'} assigned you: {task.title}",
        )
        
        return task

    def get_user_tasks(
        self,
        user_id: str,
        include_completed: bool = False,
    ) -> list[Task]:
        """Get tasks assigned to a user.
        
        Args:
            user_id: The user.
            include_completed: Include completed tasks.
        
        Returns:
            List of tasks.
        """
        tasks = [t for t in self.tasks.values() if t.assigned_to == user_id]
        
        if not include_completed:
            tasks = [t for t in tasks if t.status != TaskStatus.COMPLETED]
        
        return sorted(tasks, key=lambda t: (
            t.priority != TaskPriority.URGENT,
            t.priority != TaskPriority.HIGH,
            t.due_date or datetime.max,
        ))

    def get_overdue_tasks(self) -> list[Task]:
        """Get all overdue tasks."""
        return [t for t in self.tasks.values() if t.is_overdue]

    def get_notifications(
        self,
        user_id: str,
        unread_only: bool = True,
    ) -> list[Notification]:
        """Get notifications for a user.
        
        Args:
            user_id: The user.
            unread_only: Only return unread notifications.
        
        Returns:
            List of notifications.
        """
        notifications = [
            n for n in self.notifications.values()
            if n.user_id == user_id
        ]
        
        if unread_only:
            notifications = [n for n in notifications if not n.is_read]
        
        return sorted(notifications, key=lambda n: n.created_at, reverse=True)

    def mark_notification_read(self, notification_id: str) -> None:
        """Mark a notification as read."""
        notification = self.notifications.get(notification_id)
        if notification:
            notification.is_read = True
            notification.read_at = datetime.now()

    def mark_all_notifications_read(self, user_id: str) -> int:
        """Mark all notifications as read for a user.
        
        Returns number of notifications marked read.
        """
        count = 0
        for notification in self.notifications.values():
            if notification.user_id == user_id and not notification.is_read:
                notification.is_read = True
                notification.read_at = datetime.now()
                count += 1
        return count

    def get_activity_feed(
        self,
        entity_type: EntityType | None = None,
        entity_id: str | None = None,
        user_id: str | None = None,
        limit: int = 50,
    ) -> list[ActivityItem]:
        """Get activity feed.
        
        Args:
            entity_type: Filter by entity type.
            entity_id: Filter by entity ID.
            user_id: Filter by user.
            limit: Maximum items to return.
        
        Returns:
            List of activity items.
        """
        activities = self.activities.copy()
        
        if entity_type:
            activities = [a for a in activities if a.entity_type == entity_type]
        if entity_id:
            activities = [a for a in activities if a.entity_id == entity_id]
        if user_id:
            activities = [a for a in activities if a.user_id == user_id]
        
        return sorted(activities, key=lambda a: a.timestamp, reverse=True)[:limit]
