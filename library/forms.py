"""Forms for creating/editing library entities."""

from django import forms
from django.utils import timezone

from .models import Book, Bookmark, Borrow, Shelf, WishlistItem


class _BootstrapMixin:
    """Add Bootstrap classes to all widgets automatically."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, (forms.CheckboxInput,)):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, (forms.Select,)):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")


class ShelfForm(_BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Shelf
        fields = ["name", "location", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}


class BookForm(_BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Book
        fields = [
            "title",
            "author",
            "isbn",
            "publisher",
            "published_year",
            "total_pages",
            "genre",
            "cover_url",
            "read_status",
            "book_format",
            "shelf",
            "digital_device",
            "digital_account",
            "notes",
        ]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def clean(self):
        cleaned = super().clean()
        book_format = cleaned.get("book_format")
        shelf = cleaned.get("shelf")
        device = cleaned.get("digital_device")
        account = cleaned.get("digital_account")

        if book_format == Book.Format.DIGITAL:
            # Digital books shouldn't carry a shelf; nudge for device/account.
            if not device and not account:
                self.add_error(
                    "digital_device",
                    "For a digital book, add the device and/or the "
                    "account where it is stored.",
                )
        else:  # physical
            if device or account:
                self.add_error(
                    "book_format",
                    "Device/account only apply to digital books. "
                    "Clear them or switch the format to Digital.",
                )
        return cleaned


class BookmarkForm(_BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Bookmark
        fields = ["current_page", "note"]

    def __init__(self, *args, book: Book | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        # Prefer the explicit book; fall back to a saved instance's book.
        self.book = book
        if self.book is None and self.instance and self.instance.pk:
            self.book = self.instance.book

    def clean_current_page(self):
        page = self.cleaned_data["current_page"]
        book = self.book
        if book and book.total_pages and page > book.total_pages:
            raise forms.ValidationError(
                f"That's past the last page ({book.total_pages})."
            )
        return page


class BorrowForm(_BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Borrow
        fields = [
            "borrower_name",
            "borrower_contact",
            "borrowed_on",
            "due_on",
            "reminder_enabled",
            "notes",
        ]
        widgets = {
            "borrowed_on": forms.DateInput(attrs={"type": "date"}),
            "due_on": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def clean(self):
        cleaned = super().clean()
        borrowed_on = cleaned.get("borrowed_on") or timezone.localdate()
        due_on = cleaned.get("due_on")
        if due_on and due_on < borrowed_on:
            self.add_error(
                "due_on", "The return date can't be before the borrow date."
            )
        return cleaned


class WishlistItemForm(_BootstrapMixin, forms.ModelForm):
    class Meta:
        model = WishlistItem
        fields = [
            "title",
            "author",
            "isbn",
            "desired_format",
            "priority",
            "url",
            "notes",
        ]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}


class ReleaseBookForm(_BootstrapMixin, forms.ModelForm):
    """
    Record a book's destination when it leaves the collection
    (donated, gifted, sold, lost, etc.). The book is kept for history.
    """

    class Meta:
        model = Book
        fields = [
            "destination",
            "destination_detail",
            "released_on",
            "destination_note",
        ]
        widgets = {
            "released_on": forms.DateInput(attrs={"type": "date"}),
            "destination_note": forms.Textarea(attrs={"rows": 2}),
        }
        labels = {
            "destination_detail": "Recipient / where it went",
            "destination_note": "Note",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Require choosing a destination; default the date to today.
        self.fields["destination"].required = True
        self.fields["destination"].choices = [
            ("", "— choose —")
        ] + list(Book.Destination.choices)
        if not self.instance.released_on:
            self.fields["released_on"].initial = timezone.localdate()
