"""Template context processors for BOOKFOIL."""

from .models import Book


def undo_release(request):
    """
    Expose the most recent release(s) so templates can offer a one-click
    "undo" shortcut. Returns the single last-released book (if it is still
    released) and the size of the last bulk-released batch.
    """
    ctx = {"undo_book": None, "undo_batch_count": 0}

    # Session is not present for some requests (e.g. during errors).
    session = getattr(request, "session", None)
    if session is None:
        return ctx

    book_id = session.get("last_released_book_id")
    if book_id:
        book = (
            Book.objects.filter(
                pk=book_id, status=Book.Status.RELEASED
            ).first()
        )
        ctx["undo_book"] = book  # None if it was already restored/deleted.

    batch = session.get("last_released_batch") or []
    if batch:
        ctx["undo_batch_count"] = Book.objects.filter(
            pk__in=batch, status=Book.Status.RELEASED
        ).count()

    return ctx
