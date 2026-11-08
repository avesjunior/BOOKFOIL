from django.contrib import admin

from .models import Book, Bookmark, Borrow, Shelf, WishlistItem


class BookmarkInline(admin.StackedInline):
    model = Bookmark
    extra = 0


class BorrowInline(admin.TabularInline):
    model = Borrow
    extra = 0
    fields = (
        "borrower_name",
        "borrower_contact",
        "borrowed_on",
        "due_on",
        "reminder_enabled",
        "returned_on",
    )


@admin.register(Shelf)
class ShelfAdmin(admin.ModelAdmin):
    list_display = ("name", "location", "book_count")
    search_fields = ("name", "location")


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "author",
        "book_format",
        "location_label",
        "read_status",
        "is_borrowed_out",
    )
    list_filter = ("book_format", "read_status", "shelf", "genre")
    search_fields = ("title", "author", "isbn", "publisher")
    inlines = [BookmarkInline, BorrowInline]


@admin.register(Borrow)
class BorrowAdmin(admin.ModelAdmin):
    list_display = (
        "book",
        "borrower_name",
        "borrowed_on",
        "due_on",
        "returned_on",
        "is_overdue",
    )
    list_filter = ("reminder_enabled", "due_on")
    search_fields = ("book__title", "borrower_name", "borrower_contact")


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "author",
        "desired_format",
        "priority",
        "acquired",
    )
    list_filter = ("desired_format", "priority", "acquired")
    search_fields = ("title", "author", "isbn")


admin.site.site_header = "BOOKFOIL administration"
admin.site.site_title = "BOOKFOIL"
admin.site.index_title = "Manage your library"
