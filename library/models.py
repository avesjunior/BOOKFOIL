"""
Data models for BOOKFOIL.

Covers:
  * Shelf        - where a (physical) book lives.
  * Book         - the core CRUD entity, physical or digital.
  * Bookmark     - the page you stopped reading on.
  * Borrow       - borrower data + agreed return date / reminder alarm.
  * WishlistItem - books you want but don't own yet.
"""

from __future__ import annotations

from django.db import models
from django.urls import reverse
from django.utils import timezone


class Shelf(models.Model):
    """A location where physical books are stored."""

    name = models.CharField(max_length=120, unique=True)
    location = models.CharField(
        max_length=200,
        blank=True,
        help_text="e.g. 'Living room, top row' or 'Office cabinet'.",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "shelves"

    def __str__(self) -> str:
        return self.name

    @property
    def book_count(self) -> int:
        return self.books.count()


class Book(models.Model):
    """A book in your collection. The core CRUD entity."""

    class Format(models.TextChoices):
        PHYSICAL = "physical", "Physical"
        DIGITAL = "digital", "Digital"

    class ReadStatus(models.TextChoices):
        UNREAD = "unread", "Unread"
        READING = "reading", "Currently reading"
        FINISHED = "finished", "Finished"
        ABANDONED = "abandoned", "Abandoned"

    # --- Core bibliographic fields ---
    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255, blank=True)
    isbn = models.CharField("ISBN", max_length=20, blank=True)
    publisher = models.CharField(max_length=255, blank=True)
    published_year = models.PositiveIntegerField(null=True, blank=True)
    total_pages = models.PositiveIntegerField(null=True, blank=True)
    genre = models.CharField(max_length=120, blank=True)
    cover_url = models.URLField(blank=True)
    notes = models.TextField(blank=True)

    # --- Reading status ---
    read_status = models.CharField(
        max_length=20,
        choices=ReadStatus.choices,
        default=ReadStatus.UNREAD,
    )

    # --- Physical vs Digital ---
    book_format = models.CharField(
        "format",
        max_length=10,
        choices=Format.choices,
        default=Format.PHYSICAL,
    )

    # Physical: which shelf it lives on.
    shelf = models.ForeignKey(
        Shelf,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="books",
        help_text="Shelf where the physical copy is stored.",
    )

    # Digital: where the file/license lives.
    digital_device = models.CharField(
        max_length=150,
        blank=True,
        help_text="Device or app the digital book is on, "
        "e.g. 'Kindle Paperwhite' or 'iPad'.",
    )
    digital_account = models.CharField(
        max_length=150,
        blank=True,
        help_text="Account/store the digital book is tied to, "
        "e.g. 'Amazon (jane@…)' or 'Google Play Books'.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]

    def __str__(self) -> str:
        if self.author:
            return f"{self.title} — {self.author}"
        return self.title

    def get_absolute_url(self) -> str:
        return reverse("library:book_detail", args=[self.pk])

    # --- Convenience helpers ---
    @property
    def is_digital(self) -> bool:
        return self.book_format == self.Format.DIGITAL

    @property
    def is_physical(self) -> bool:
        return self.book_format == self.Format.PHYSICAL

    @property
    def location_label(self) -> str:
        """Human readable 'where is it' string."""
        if self.is_digital:
            parts = [p for p in (self.digital_device, self.digital_account) if p]
            return " / ".join(parts) if parts else "Digital"
        return self.shelf.name if self.shelf else "No shelf assigned"

    @property
    def active_borrow(self) -> "Borrow | None":
        """The current outstanding loan, if the book is lent out."""
        return self.borrows.filter(returned_on__isnull=True).first()

    @property
    def is_borrowed_out(self) -> bool:
        return self.active_borrow is not None

    @property
    def reading_progress(self) -> int | None:
        """Percentage read based on the bookmark, if available."""
        bm = getattr(self, "bookmark", None)
        if not bm or not self.total_pages:
            return None
        return min(100, round((bm.current_page / self.total_pages) * 100))


class Bookmark(models.Model):
    """Tracks the page where you stopped reading a book."""

    book = models.OneToOneField(
        Book,
        on_delete=models.CASCADE,
        related_name="bookmark",
    )
    current_page = models.PositiveIntegerField(default=0)
    note = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional note, e.g. 'end of chapter 4'.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"{self.book.title} — page {self.current_page}"

    @property
    def percent(self) -> int | None:
        if not self.book.total_pages:
            return None
        return min(
            100, round((self.current_page / self.book.total_pages) * 100)
        )


class Borrow(models.Model):
    """
    Records that a book has been lent to someone, with the borrower's
    contact details and an agreed return date that acts as a reminder/alarm.
    """

    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name="borrows",
    )
    borrower_name = models.CharField(max_length=200)
    borrower_contact = models.CharField(
        max_length=255,
        blank=True,
        help_text="Phone, email or however you reach them.",
    )
    borrowed_on = models.DateField(default=timezone.localdate)
    due_on = models.DateField(
        help_text="Agreed date to return the book. Used for reminders.",
    )
    reminder_enabled = models.BooleanField(
        default=True,
        help_text="Flag this loan for return reminders.",
    )
    returned_on = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["due_on"]

    def __str__(self) -> str:
        return f"{self.book.title} → {self.borrower_name}"

    @property
    def is_returned(self) -> bool:
        return self.returned_on is not None

    @property
    def is_active(self) -> bool:
        return self.returned_on is None

    @property
    def is_overdue(self) -> bool:
        """True if still out and past the agreed return date."""
        return self.is_active and self.due_on < timezone.localdate()

    @property
    def days_until_due(self) -> int:
        """Negative when overdue, 0 on the due date, positive when upcoming."""
        return (self.due_on - timezone.localdate()).days

    def mark_returned(self, when=None) -> None:
        self.returned_on = when or timezone.localdate()
        self.save(update_fields=["returned_on"])


class WishlistItem(models.Model):
    """A book you want to read/own but don't have yet."""

    class Priority(models.IntegerChoices):
        LOW = 1, "Low"
        MEDIUM = 2, "Medium"
        HIGH = 3, "High"

    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255, blank=True)
    isbn = models.CharField("ISBN", max_length=20, blank=True)
    desired_format = models.CharField(
        max_length=10,
        choices=Book.Format.choices,
        default=Book.Format.PHYSICAL,
    )
    priority = models.IntegerField(
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )
    url = models.URLField(
        blank=True,
        help_text="Link to a store/listing for the book.",
    )
    notes = models.TextField(blank=True)
    acquired = models.BooleanField(
        default=False,
        help_text="Tick once you own it.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["acquired", "-priority", "title"]

    def __str__(self) -> str:
        return self.title
