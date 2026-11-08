"""
Report books that are overdue or due soon for return.

Run manually or from cron to act as the "ask the book back" alarm:

    python manage.py check_reminders
    python manage.py check_reminders --within 3

Exit status is 1 when there are overdue loans, so it can gate shell scripts.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from library.models import Borrow


class Command(BaseCommand):
    help = "List borrowed books that are overdue or due within N days."

    def add_arguments(self, parser):
        parser.add_argument(
            "--within",
            type=int,
            default=7,
            help="Days ahead to include as 'due soon' (default: 7).",
        )

    def handle(self, *args, **options):
        within = options["within"]
        today = timezone.localdate()

        active = (
            Borrow.objects.filter(
                returned_on__isnull=True, reminder_enabled=True
            )
            .select_related("book")
            .order_by("due_on")
        )

        overdue = [b for b in active if b.is_overdue]
        due_soon = [b for b in active if 0 <= b.days_until_due <= within]

        if overdue:
            self.stdout.write(self.style.ERROR("OVERDUE — ask these back:"))
            for b in overdue:
                self.stdout.write(
                    f"  • {b.book.title} — {b.borrower_name} "
                    f"({b.borrower_contact or 'no contact'}) "
                    f"due {b.due_on} [{-b.days_until_due} day(s) late]"
                )

        if due_soon:
            self.stdout.write(
                self.style.WARNING(f"\nDue within {within} day(s):")
            )
            for b in due_soon:
                self.stdout.write(
                    f"  • {b.book.title} — {b.borrower_name} "
                    f"due {b.due_on} [in {b.days_until_due} day(s)]"
                )

        if not overdue and not due_soon:
            self.stdout.write(
                self.style.SUCCESS("Nothing due. All good.")
            )

        if overdue:
            raise SystemExit(1)
