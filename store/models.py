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
# Issuance
# =========================
class Issuance(models.Model):
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

    @property
    def can_reverse(self):
        if self.is_reversed:
            return False
        return timezone.now() <= self.issued_at + timedelta(hours=6)

    @property
    def status(self):
        if self.is_reversed:
            return "Reversed"
        if self.can_reverse:
            return "Active"
        return "Locked"

    def __str__(self):
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
        ISSUANCE_REVERSED = "ISSUANCE_REVERSED", "Issuance reversed"
        ISSUANCE_FAILED = "ISSUANCE_FAILED", "Issuance failed"
        LOW_STOCK_ALERT = "LOW_STOCK_ALERT", "Low stock alert"

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
        help_text="Model name e.g. Issuance, StockIn, Item",
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
