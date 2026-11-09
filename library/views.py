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
    ReleaseBookForm,
    ShelfForm,
    ShelfReleaseForm,
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
        "book_count": Book.objects.filter(status=Book.Status.ACTIVE).count(),
        "shelf_count": Shelf.objects.count(),
        "reading": Book.objects.filter(
            status=Book.Status.ACTIVE,
            read_status=Book.ReadStatus.READING,
        ).order_by("title"),
        "active_borrows": active_borrows,
        "overdue": overdue,
        "due_soon": due_soon,
        "wishlist_open": WishlistItem.objects.filter(acquired=False).count(),
        "released_count": Book.objects.filter(
            status=Book.Status.RELEASED
        ).count(),
        "today": today,
    }
    return render(request, "library/dashboard.html", context)


# --------------------------------------------------------------------------- #
# Book CRUD
# --------------------------------------------------------------------------- #
def book_list(request):
    # The main list shows books still in your collection. Released books
    # (donated, gifted, etc.) move to the archive/history view.
    books = Book.objects.select_related("shelf").filter(
        status=Book.Status.ACTIVE
    )

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
# Destination — release a book (donate/gift/…), archive & restore
# --------------------------------------------------------------------------- #
def book_release(request, pk):
    """Record where a book went and move it out of the active collection."""
    book = get_object_or_404(Book, pk=pk)

    if book.is_released:
        messages.info(request, f"“{book.title}” has already been released.")
        return redirect(book.get_absolute_url())

    if book.is_borrowed_out:
        messages.warning(
            request,
            f"“{book.title}” is currently lent to "
            f"{book.active_borrow.borrower_name}. Mark it returned before "
            "releasing it.",
        )
        return redirect(book.get_absolute_url())

    form = ReleaseBookForm(request.POST or None, instance=book)
    if request.method == "POST" and form.is_valid():
        book = form.save(commit=False)
        book.status = Book.Status.RELEASED
        book.save(
            update_fields=[
                "status",
                "destination",
                "destination_detail",
                "released_on",
                "destination_note",
                "updated_at",
            ]
        )
        # Remember this release so we can offer a one-click undo.
        request.session["last_released_book_id"] = book.pk
        messages.success(
            request,
            f"“{book.title}” was marked as "
            f"{book.get_destination_display().lower()} and moved to your "
            "history. It's kept for the record.",
        )
        return redirect(book.get_absolute_url())

    return render(
        request,
        "library/book_release_form.html",
        {"form": form, "book": book},
    )


def book_restore(request, pk):
    """Bring a released book back into the active collection."""
    book = get_object_or_404(Book, pk=pk)
    if request.method == "POST":
        book.restore()
        # Clear any pending "undo" pointer for this book.
        if request.session.get("last_released_book_id") == book.pk:
            request.session.pop("last_released_book_id", None)
        messages.success(
            request, f"“{book.title}” is back in your collection."
        )
    # Honour an explicit redirect target (e.g. the undo button on a list).
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt:
        return redirect(nxt)
    return redirect(book.get_absolute_url())


def book_archive(request):
    """History of books that have left the collection (incl. already read)."""
    books = Book.objects.select_related("shelf").filter(
        status=Book.Status.RELEASED
    )

    query = request.GET.get("q", "").strip()
    destination = request.GET.get("destination", "").strip()
    read_only = request.GET.get("read", "").strip()  # "1" => only finished

    if query:
        books = books.filter(
            Q(title__icontains=query)
            | Q(author__icontains=query)
            | Q(isbn__icontains=query)
            | Q(destination_detail__icontains=query)
        )
    if destination in dict(Book.Destination.choices):
        books = books.filter(destination=destination)
    if read_only == "1":
        books = books.filter(read_status=Book.ReadStatus.FINISHED)

    books = books.order_by("-released_on", "title")

    context = {
        "books": books,
        "destinations": Book.Destination.choices,
        "q": query,
        "selected_destination": destination,
        "read_only": read_only == "1",
    }
    return render(request, "library/book_archive.html", context)


def shelf_release(request, pk):
    """
    Release every active book on a shelf in one go (e.g. donate a whole
    shelf). Shows a confirmation list before anything changes.
    """
    shelf = get_object_or_404(Shelf, pk=pk)
    books = shelf.books.filter(status=Book.Status.ACTIVE).order_by("title")

    # Books currently lent out can't be released — surface them separately.
    releasable = [b for b in books if not b.is_borrowed_out]
    lent_out = [b for b in books if b.is_borrowed_out]

    form = ShelfReleaseForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        if not releasable:
            messages.warning(
                request,
                f"No releasable books on “{shelf.name}”.",
            )
            return redirect("library:shelf_list")

        cd = form.cleaned_data
        released_ids = []
        for book in releasable:
            book.release(
                destination=cd["destination"],
                detail=cd["destination_detail"],
                note=cd["destination_note"],
                when=cd["released_on"],
            )
            released_ids.append(book.pk)

        # Remember the batch so it can be undone in one click.
        request.session["last_released_batch"] = released_ids
        messages.success(
            request,
            f"Released {len(released_ids)} book(s) from “{shelf.name}” "
            f"as {dict(Book.Destination.choices)[cd['destination']].lower()}. "
            "They're kept in your history.",
        )
        skipped = len(lent_out)
        if skipped:
            messages.info(
                request,
                f"{skipped} book(s) were skipped because they're lent out.",
            )
        return redirect("library:book_archive")

    context = {
        "shelf": shelf,
        "form": form,
        "releasable": releasable,
        "lent_out": lent_out,
    }
    return render(request, "library/shelf_release_form.html", context)


def undo_last_batch_release(request):
    """Restore the most recently bulk-released set of books."""
    ids = request.session.get("last_released_batch") or []
    if request.method == "POST" and ids:
        restored = 0
        for book in Book.objects.filter(pk__in=ids):
            book.restore()
            restored += 1
        request.session.pop("last_released_batch", None)
        messages.success(
            request,
            f"Undone — {restored} book(s) returned to your collection.",
        )
    nxt = request.POST.get("next") or request.GET.get("next")
    return redirect(nxt or "library:book_archive")


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
