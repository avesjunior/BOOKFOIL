"""Views for BOOKFOIL: book CRUD, bookmark, borrowing and wishlist."""

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import (
    BookForm,
    BookmarkForm,
    BorrowForm,
    ShelfForm,
    WishlistItemForm,
)
from .models import Book, Borrow, Shelf, WishlistItem


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
def dashboard(request):
    today = timezone.localdate()
    active_borrows = (
        Borrow.objects.filter(returned_on__isnull=True)
        .select_related("book")
        .order_by("due_on")
    )
    overdue = [b for b in active_borrows if b.is_overdue]
    due_soon = [
        b for b in active_borrows if 0 <= b.days_until_due <= 7
    ]
    context = {
        "book_count": Book.objects.count(),
        "shelf_count": Shelf.objects.count(),
        "reading": Book.objects.filter(
            read_status=Book.ReadStatus.READING
        ).order_by("title"),
        "active_borrows": active_borrows,
        "overdue": overdue,
        "due_soon": due_soon,
        "wishlist_open": WishlistItem.objects.filter(acquired=False).count(),
        "today": today,
    }
    return render(request, "library/dashboard.html", context)


# --------------------------------------------------------------------------- #
# Book CRUD
# --------------------------------------------------------------------------- #
def book_list(request):
    books = Book.objects.select_related("shelf").all()

    query = request.GET.get("q", "").strip()
    fmt = request.GET.get("format", "").strip()
    shelf_id = request.GET.get("shelf", "").strip()
    status = request.GET.get("status", "").strip()

    if query:
        books = books.filter(
            Q(title__icontains=query)
            | Q(author__icontains=query)
            | Q(isbn__icontains=query)
            | Q(genre__icontains=query)
        )
    if fmt in dict(Book.Format.choices):
        books = books.filter(book_format=fmt)
    if shelf_id.isdigit():
        books = books.filter(shelf_id=int(shelf_id))
    if status in dict(Book.ReadStatus.choices):
        books = books.filter(read_status=status)

    context = {
        "books": books,
        "shelves": Shelf.objects.all(),
        "formats": Book.Format.choices,
        "statuses": Book.ReadStatus.choices,
        "q": query,
        "selected_format": fmt,
        "selected_shelf": shelf_id,
        "selected_status": status,
    }
    return render(request, "library/book_list.html", context)


def book_detail(request, pk):
    book = get_object_or_404(
        Book.objects.select_related("shelf"), pk=pk
    )
    context = {
        "book": book,
        "bookmark": getattr(book, "bookmark", None),
        "active_borrow": book.active_borrow,
        "borrow_history": book.borrows.order_by("-borrowed_on"),
    }
    return render(request, "library/book_detail.html", context)


def book_create(request):
    form = BookForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        book = form.save()
        messages.success(request, f"Added “{book.title}”.")
        return redirect(book.get_absolute_url())
    return render(
        request,
        "library/book_form.html",
        {"form": form, "title": "Add a book"},
    )


def book_update(request, pk):
    book = get_object_or_404(Book, pk=pk)
    form = BookForm(request.POST or None, instance=book)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Updated “{book.title}”.")
        return redirect(book.get_absolute_url())
    return render(
        request,
        "library/book_form.html",
        {"form": form, "title": f"Edit “{book.title}”", "book": book},
    )


def book_delete(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if request.method == "POST":
        title = book.title
        book.delete()
        messages.success(request, f"Deleted “{title}”.")
        return redirect("library:book_list")
    return render(request, "library/confirm_delete.html", {
        "object": book,
        "object_label": f"book “{book.title}”",
        "cancel_url": book.get_absolute_url(),
    })


# --------------------------------------------------------------------------- #
# Bookmark — track the page you stopped on
# --------------------------------------------------------------------------- #
def bookmark_edit(request, pk):
    book = get_object_or_404(Book, pk=pk)
    bookmark = getattr(book, "bookmark", None)
    form = BookmarkForm(request.POST or None, instance=bookmark, book=book)
    if request.method == "POST" and form.is_valid():
        bm = form.save(commit=False)
        bm.book = book
        bm.save()
        # Reading a bookmark implies you're reading the book.
        if book.read_status == Book.ReadStatus.UNREAD:
            book.read_status = Book.ReadStatus.READING
            book.save(update_fields=["read_status"])
        messages.success(
            request, f"Bookmark saved at page {bm.current_page}."
        )
        return redirect(book.get_absolute_url())
    return render(
        request,
        "library/bookmark_form.html",
        {"form": form, "book": book},
    )


# --------------------------------------------------------------------------- #
# Borrowing — lend a book, set a return reminder, mark returned
# --------------------------------------------------------------------------- #
def borrow_create(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if book.is_borrowed_out:
        messages.warning(
            request,
            f"“{book.title}” is already lent to "
            f"{book.active_borrow.borrower_name}.",
        )
        return redirect(book.get_absolute_url())

    form = BorrowForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        borrow = form.save(commit=False)
        borrow.book = book
        borrow.save()
        messages.success(
            request,
            f"Lent “{book.title}” to {borrow.borrower_name}. "
            f"Return reminder set for {borrow.due_on}.",
        )
        return redirect(book.get_absolute_url())
    return render(
        request,
        "library/borrow_form.html",
        {"form": form, "book": book},
    )


def borrow_return(request, pk):
    borrow = get_object_or_404(Borrow, pk=pk)
    if request.method == "POST":
        borrow.mark_returned()
        messages.success(
            request,
            f"Marked “{borrow.book.title}” as returned by "
            f"{borrow.borrower_name}.",
        )
    return redirect(borrow.book.get_absolute_url())


def borrow_list(request):
    """All loans, with overdue/upcoming reminders highlighted."""
    show = request.GET.get("show", "active")
    qs = Borrow.objects.select_related("book").all()
    if show == "active":
        qs = qs.filter(returned_on__isnull=True)
    elif show == "returned":
        qs = qs.filter(returned_on__isnull=False)
    elif show == "overdue":
        qs = [b for b in qs.filter(returned_on__isnull=True) if b.is_overdue]
    context = {
        "borrows": qs,
        "show": show,
        "today": timezone.localdate(),
    }
    return render(request, "library/borrow_list.html", context)


# --------------------------------------------------------------------------- #
# Shelves
# --------------------------------------------------------------------------- #
def shelf_list(request):
    return render(
        request,
        "library/shelf_list.html",
        {"shelves": Shelf.objects.all()},
    )


def shelf_create(request):
    form = ShelfForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        shelf = form.save()
        messages.success(request, f"Added shelf “{shelf.name}”.")
        return redirect("library:shelf_list")
    return render(
        request,
        "library/shelf_form.html",
        {"form": form, "title": "Add a shelf"},
    )


def shelf_update(request, pk):
    shelf = get_object_or_404(Shelf, pk=pk)
    form = ShelfForm(request.POST or None, instance=shelf)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Updated shelf “{shelf.name}”.")
        return redirect("library:shelf_list")
    return render(
        request,
        "library/shelf_form.html",
        {"form": form, "title": f"Edit “{shelf.name}”"},
    )


def shelf_delete(request, pk):
    shelf = get_object_or_404(Shelf, pk=pk)
    if request.method == "POST":
        name = shelf.name
        shelf.delete()
        messages.success(request, f"Deleted shelf “{name}”.")
        return redirect("library:shelf_list")
    return render(request, "library/confirm_delete.html", {
        "object": shelf,
        "object_label": f"shelf “{shelf.name}” "
        f"({shelf.book_count} book(s) will be unassigned)",
        "cancel_url": reverse("library:shelf_list"),
    })


# --------------------------------------------------------------------------- #
# Wishlist
# --------------------------------------------------------------------------- #
def wishlist(request):
    items = WishlistItem.objects.all()
    return render(request, "library/wishlist.html", {"items": items})


def wishlist_create(request):
    form = WishlistItemForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        item = form.save()
        messages.success(request, f"Added “{item.title}” to your wishlist.")
        return redirect("library:wishlist")
    return render(
        request,
        "library/wishlist_form.html",
        {"form": form, "title": "Add to wishlist"},
    )


def wishlist_update(request, pk):
    item = get_object_or_404(WishlistItem, pk=pk)
    form = WishlistItemForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Updated “{item.title}”.")
        return redirect("library:wishlist")
    return render(
        request,
        "library/wishlist_form.html",
        {"form": form, "title": f"Edit “{item.title}”"},
    )


def wishlist_toggle_acquired(request, pk):
    item = get_object_or_404(WishlistItem, pk=pk)
    if request.method == "POST":
        item.acquired = not item.acquired
        item.save(update_fields=["acquired"])
        state = "acquired" if item.acquired else "still wanted"
        messages.success(request, f"“{item.title}” marked as {state}.")
    return redirect("library:wishlist")


def wishlist_delete(request, pk):
    item = get_object_or_404(WishlistItem, pk=pk)
    if request.method == "POST":
        title = item.title
        item.delete()
        messages.success(request, f"Removed “{title}” from your wishlist.")
        return redirect("library:wishlist")
    return render(request, "library/confirm_delete.html", {
        "object": item,
        "object_label": f"wishlist item “{item.title}”",
        "cancel_url": reverse("library:wishlist"),
    })
