from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta


# =========================
# Department
# =========================
class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name



# =========================
# Category
# =========================
class Category(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


# =========================
# Item
# =========================
class Item(models.Model):
    name = models.CharField(max_length=200, unique=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="items",
    )
    quantity = models.PositiveIntegerField(default=0)
    description = models.CharField(max_length=500, blank=True, null=True)

    UOM_CHOICES = [
        ("pkts", "Pkts"),
        ("pcs", "Pcs"),
        ("bundles", "Bundles"),
        ("dozen", "Dozen"),
        ("pairs", "Pairs"),
        ("rolls", "Rolls"),
    ]

    unit_of_measurement = models.CharField(max_length=50, choices=UOM_CHOICES)
    reorder_level = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("category", "name")

    def __str__(self):
        return f"{self.name} ({self.unit_of_measurement})"

    @property
    def status(self):
        if self.quantity == 0:
            return "Out of Stock"
        if self.quantity <= self.reorder_level:
            return "Low Stock"
        return "In Stock"


# =========================
# Staff
# =========================
class Staff(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_profile",
    )
    staff_id = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=150)
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staffs",
    )

    ROLES_CHOICES = [
        ("project manager", "Project Manager"),
        ("quality control", "Quality Control"),
        ("project engineer", "Project Engineer"),
        ("RA manager", "RA Manager"),
        ("box keeper", "Box Keeper"),
        ("planner", "Planner"),
        ("site_admin", "Site Admin"),
        ("logistics", "Logistics"),
        ("store-keeper", "Store-Keeper"),
        ("purchasing officer", "Purchasing Officer"),
        ("transport officer", "Transport Officer"),
        ("hse coordinator", "HSE Coordinator"),
        ("supervisor", "Supervisor"),
        ("team lead", "Team Lead"),
        ("worker", "Worker"),
    ]

    job_roles = models.CharField(max_length=50, choices=ROLES_CHOICES)

    def __str__(self):
        return f"{self.name} ({self.staff_id})"

    def role_display(self):
        return self.get_job_roles_display()


# =========================
# Stock In
# =========================
class StockIn(models.Model):
    received_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="stocks",
    )
    document = models.FileField(
        upload_to="stock_document/",
        blank=True,
        null=True,
    )
    comment = models.TextField(blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"StockIn #{self.id}"


class StockInItem(models.Model):
    stockin = models.ForeignKey(
        StockIn,
        related_name="lines",
        on_delete=models.CASCADE,
    )
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["stockin", "item"],
                name="unique_item_per_stockin",
            ),
            models.CheckConstraint(
                check=Q(quantity__gt=0),
                name="stockinitem_quantity_gt_zero",
            ),
        ]

    def __str__(self):
        return f"StockInItem: {self.item.name} ({self.quantity})"


# =========================
# Request
# =========================
class Request(models.Model):
    class Status(models.TextChoices):
        DRAFT     = "draft",     "Draft"
        PENDING   = "pending",   "Pending Approval"
        APPROVED  = "approved",  "Approved"
        REJECTED  = "rejected",  "Rejected"
        ESCALATED = "escalated", "Escalated"
        FULFILLED = "fulfilled", "Fulfilled"
        LOCKED    = "locked",    "Locked"

    requester = models.ForeignKey(
        Staff,
        on_delete=models.PROTECT,
        related_name="requests",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    # True means a submitted request was edited and needs explicit re-submission.
    needs_resubmission = models.BooleanField(default=False)
    purpose = models.TextField(blank=True)
    store_note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    fulfilled_at = models.DateTimeField(null=True, blank=True)
    editable_until = models.DateTimeField(null=True, blank=True)

    fulfilled_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="fulfilled_requests",
    )

    # Supervisor approval fields
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="approved_requests",
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="rejected_requests",
    )
    rejection_reason = models.TextField(blank=True)
    escalated_at = models.DateTimeField(null=True, blank=True)
    supervisor_deadline = models.DateTimeField(null=True, blank=True)

    last_edited_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="edited_requests",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["submitted_at"]),
            models.Index(fields=["fulfilled_at"]),
        ]
        permissions = [
            ("can_approve_requests", "Can approve store requests"),
        ]

    def __str__(self):
        return f"Request #{self.id} by {self.requester.name}"

    @property
    def is_fulfilled(self):
        return self.status == self.Status.FULFILLED

    @property
    def is_locked(self):
        return self.status == self.Status.LOCKED

    @property
    def can_staff_edit(self):
        return self.status in {
            self.Status.DRAFT,
            self.Status.PENDING,
        } and self.fulfilled_at is None

    @property
    def can_staff_submit(self):
        if self.status == self.Status.DRAFT:
            return True
        if self.status == self.Status.PENDING:
            return self.needs_resubmission
        return False

    @property
    def was_edited_before_fulfillment(self):
        if self.status not in {self.Status.FULFILLED, self.Status.LOCKED}:
            return False
        edited_qs = self.activities.filter(action__in=[RequestActivity.Action.STAFF_EDITED, RequestActivity.Action.STORE_EDITED])
        if self.fulfilled_at is not None:
            edited_qs = edited_qs.filter(created_at__lte=self.fulfilled_at)
        return edited_qs.exists()

    @property
    def display_status_slug(self):
        return "edited" if self.was_edited_before_fulfillment else self.status

    @property
    def display_status_label(self):
        return "Edited" if self.was_edited_before_fulfillment else self.get_status_display()

    @property
    def can_store_edit_fulfillment(self):
        if self.fulfilled_at is None or self.editable_until is None:
            return False
        return timezone.now() <= self.editable_until

    def mark_submitted(self):
        from store.services.sla_service import compute_supervisor_deadline
        now = timezone.now()
        self.status = self.Status.PENDING
        self.submitted_at = now
        self.needs_resubmission = False
        self.supervisor_deadline = compute_supervisor_deadline(now)
        self.save(update_fields=[
            "status",
            "submitted_at",
            "needs_resubmission",
            "supervisor_deadline",
            "updated_at",
        ])

    def mark_approved(self, user):
        now = timezone.now()
        self.status = self.Status.APPROVED
        self.approved_at = now
        self.approved_by = user
        self.save(update_fields=[
            "status", "approved_at", "approved_by", "updated_at"
        ])

    def mark_rejected(self, user, reason):
        now = timezone.now()
        self.status = self.Status.REJECTED
        self.rejected_at = now
        self.rejected_by = user
        self.rejection_reason = reason
        self.save(update_fields=[
            "status", "rejected_at", "rejected_by",
            "rejection_reason", "updated_at"
        ])

    def mark_escalated(self):
        now = timezone.now()
        self.status = self.Status.ESCALATED
        self.escalated_at = now
        self.save(update_fields=["status", "escalated_at", "updated_at"])

    def mark_fulfilled(self, user):
        now = timezone.now()
        self.status = self.Status.FULFILLED
        self.fulfilled_at = now
        self.editable_until = now + timedelta(hours=6)
        self.fulfilled_by = user
        self.last_edited_by = user
        self.save(
            update_fields=[
                "status",
                "fulfilled_at",
                "editable_until",
                "fulfilled_by",
                "last_edited_by",
                "updated_at",
            ]
        )

    def lock_if_due(self):
        if self.status == self.Status.FULFILLED and self.editable_until and timezone.now() > self.editable_until:
            self.status = self.Status.LOCKED
            self.save(update_fields=["status", "updated_at"])


class RequestItem(models.Model):
    request = models.ForeignKey(
        Request,
        on_delete=models.CASCADE,
        related_name="items",
    )
    item = models.ForeignKey(
        Item,
        on_delete=models.PROTECT,
        related_name="request_items",
    )
    requested_qty = models.PositiveIntegerField()
    # Immutable cap used for storekeeper pre-fulfillment edits.
    # Storekeeper may decrease and later increase, but never beyond this value.
    original_requested_qty = models.PositiveIntegerField(default=0)
    fulfilled_qty = models.PositiveIntegerField(default=0)
    # Set by supervisor at approval time. Storekeeper ceiling — cannot fulfill beyond this.
    # Null means not yet approved (request still pending or rejected).
    approved_qty = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["request", "item"],
                name="unique_item_per_request",
            ),
            models.CheckConstraint(
                check=Q(requested_qty__gt=0),
                name="requestitem_requested_qty_gt_zero",
            ),
        ]

    def __str__(self):
        return f"{self.item.name} on Request #{self.request.id}"


    def save(self, *args, **kwargs):
        if not self.original_requested_qty:
            self.original_requested_qty = self.requested_qty
        super().save(*args, **kwargs)
    @property
    def can_increase_fulfilled_qty(self):
        ceiling = self.approved_qty if self.approved_qty is not None else self.requested_qty
        return self.fulfilled_qty < ceiling


class RequestActivity(models.Model):
    class Action(models.TextChoices):
        CREATED            = "created",            "Created"
        STAFF_EDITED       = "staff_edited",       "Staff edited"
        STORE_EDITED       = "store_edited",       "Store edited"
        SUBMITTED          = "submitted",          "Submitted"
        FULFILLED          = "fulfilled",          "Fulfilled"
        FULFILLMENT_EDITED = "fulfillment_edited", "Fulfillment edited"
        LOCKED             = "locked",             "Locked"
        SUPERVISOR_EDITED  = "supervisor_edited",  "Supervisor edited"
        APPROVED           = "approved",           "Approved"
        REJECTED           = "rejected",           "Rejected"
        ESCALATED          = "escalated",          "Escalated"
        PENDING            = "pending",            "Pending"

    request = models.ForeignKey(
        Request,
        on_delete=models.CASCADE,
        related_name="activities",
    )
    actor = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="request_activities",
    )
    action = models.CharField(
        max_length=50,
        choices=Action.choices,
        db_index=True,
    )
    description = models.CharField(max_length=255)
    metadata = models.JSONField(blank=True, default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.get_action_display()} on Request #{self.request.id}"


# =========================
# Issuance
# =========================
class Issuance(models.Model):
    request = models.OneToOneField(
        Request,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="issuance",
    )
    staff = models.ForeignKey(
        Staff,
        on_delete=models.PROTECT,
        related_name="issuances",
    )
    issued_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="issued_issuances",
    )

    # Transitional legacy fields kept only for compatibility with historical records.\n    # They are intentionally unused by the active request-based issuance workflow.\n    # Do not re-enable reversal/manual issuance paths.
    is_reversed = models.BooleanField(default=False)
    reversed_at = models.DateTimeField(null=True, blank=True)
    reversed_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reversal_actions",
    )

    comment = models.TextField(blank=True)
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issued_at"]
        indexes = [
            models.Index(fields=["issued_at"]),
        ]

    @property
    def can_reverse(self):
        # Transitional compatibility for old UI.
        if self.is_reversed:
            return False
        return timezone.now() <= self.issued_at + timedelta(hours=6)

    @property
    def can_edit(self):
        if self.is_reversed:
            return False
        if self.request and self.request.editable_until:
            return timezone.now() <= self.request.editable_until
        return timezone.now() <= self.issued_at + timedelta(hours=6)

    @property
    def status(self):
        if self.is_reversed:
            return "Reversed"
        if self.can_edit:
            return "Editable"
        return "Locked"

    def __str__(self):
        if self.request_id:
            return f"Issuance #{self.id} for Request #{self.request_id}"
        return f"Issuance #{self.id} to {self.staff.name}"


class IssuanceItem(models.Model):
    item = models.ForeignKey(
        Item,
        on_delete=models.PROTECT,
        related_name="issuance_items",
    )
    quantity = models.PositiveIntegerField()
    issuance = models.ForeignKey(
        Issuance,
        on_delete=models.CASCADE,
        related_name="items",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["issuance", "item"],
                name="unique_item_per_issuance",
            ),
            models.CheckConstraint(
                check=Q(quantity__gt=0),
                name="issuanceitem_quantity_gt_zero",
            ),
        ]

    def __str__(self):
        return f"Issued {self.item.name} ({self.quantity}) in Issuance #{self.issuance.id}"


# =========================
# Activity (Audit / Visibility Spine)
# =========================
class Activity(models.Model):
    class Verb(models.TextChoices):
        STOCKIN_CREATED = "STOCKIN_CREATED", "Stock-in created"
        ISSUANCE_CREATED = "ISSUANCE_CREATED", "Issuance created"
        ISSUANCE_UPDATED = "ISSUANCE_UPDATED", "Issuance updated"
        ISSUANCE_REVERSED = "ISSUANCE_REVERSED", "Issuance reversed"
        ISSUANCE_FAILED = "ISSUANCE_FAILED", "Issuance failed"
        LOW_STOCK_ALERT = "LOW_STOCK_ALERT", "Low stock alert"
        REQUEST_CREATED = "REQUEST_CREATED", "Request created"
        REQUEST_UPDATED = "REQUEST_UPDATED", "Request updated"
        REQUEST_SUBMITTED = "REQUEST_SUBMITTED", "Request submitted"
        REQUEST_FULFILLED = "REQUEST_FULFILLED", "Request fulfilled"
        REQUEST_PENDING   = "REQUEST_PENDING",   "Request pending approval"
        REQUEST_APPROVED  = "REQUEST_APPROVED",  "Request approved"
        REQUEST_REJECTED  = "REQUEST_REJECTED",  "Request rejected"
        REQUEST_ESCALATED = "REQUEST_ESCALATED", "Request escalated"

    actor = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="activities",
    )

    verb = models.CharField(
        max_length=50,
        choices=Verb.choices,
    )

    target_type = models.CharField(
        max_length=50,
        help_text="Model name e.g. Issuance, StockIn, Item, Request",
    )
    target_id = models.PositiveIntegerField(
        help_text="Primary key of the affected object",
    )

    summary = models.CharField(max_length=255)

    metadata = models.JSONField(blank=True, default=dict)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["verb"]),
            models.Index(fields=["target_type", "target_id"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.get_verb_display()} by {self.actor}"

class UserProfile(models.Model):
    """
    Lightweight extension for plain Django User objects
    (Management, StoreKeeper). Holds the supervisor toggle.
    Only one user may be active supervisor at a time.
    This is enforced at the model save level, not just the UI.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    is_active_supervisor = models.BooleanField(default=False)
    supervisor_since = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.is_active_supervisor:
            UserProfile.objects.exclude(pk=self.pk).filter(
                is_active_supervisor=True
            ).update(
                is_active_supervisor=False,
                supervisor_since=None,
            )
            if not self.supervisor_since:
                self.supervisor_since = timezone.now()
        else:
            self.supervisor_since = None
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Profile of {self.user.username}"


# =========================
# Notification
# =========================
class Notification(models.Model):
    class EventType(models.TextChoices):
        STOCKIN_CREATED   = "stockin_created",   "Stock-in created"
        ISSUANCE_CREATED  = "issuance_created",  "Issuance created"
        ISSUANCE_UPDATED  = "issuance_updated",  "Issuance updated"
        ISSUANCE_REVERSED = "issuance_reversed", "Issuance reversed"
        ISSUANCE_FAILED   = "issuance_failed",   "Issuance failed"
        LOW_STOCK_ALERT   = "low_stock_alert",   "Low stock alert"
        REQUEST_CREATED   = "request_created",   "Request created"
        REQUEST_UPDATED   = "request_updated",   "Request updated"
        REQUEST_SUBMITTED = "REQUEST_SUBMITTED", "Request submitted"
        REQUEST_FULFILLED = "REQUEST_FULFILLED", "Request fulfilled"
        REQUEST_APPROVED  = "request_approved",  "Request approved"
        REQUEST_REJECTED  = "request_rejected",  "Request rejected"
        REQUEST_ESCALATED = "request_escalated", "Request escalated"
        REQUEST_PENDING   = "request_pending",   "Request pending approval"

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    event_type = models.CharField(max_length=50, choices=EventType.choices, db_index=True)
    message = models.TextField()
    target_type = models.CharField(max_length=50, blank=True)
    target_id = models.PositiveIntegerField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"Notification to {self.recipient.username}: {self.event_type}"


