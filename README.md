# 📚 BOOKFOIL

A personal book-management web app built with **Python + Django** and a
local **SQLite** database.

## Features

- **Book CRUD** — add, view, edit and delete books with title, author, ISBN,
  publisher, year, pages, genre, cover image and notes.
- **Shelves** — organise physical books by shelf (name + location), and see
  how many books each shelf holds.
- **Physical vs Digital** — mark each book's format. Digital books record the
  **device** (e.g. Kindle, iPad) and the **account/store** they live on.
- **Bookmark** — track the page you stopped reading on, with an optional note
  and a reading-progress bar.
- **Borrowing** — lend a book, record the borrower's name and contact, the
  borrow date and the agreed **return date**.
- **Return reminders / alarm** — the dashboard highlights overdue loans and
  loans due within 7 days. A `check_reminders` management command can be run
  from cron to act as the "ask the book back" alarm.
- **Wishlist** — keep a list of books you want, with desired format, priority,
  a store link and an "acquired" toggle.
- **Admin** — full Django admin for power editing.

## Requirements

- Python 3.10+
- Django 5.x (see `requirements.txt`)

## Setup

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate

# 2. Install dependencies (needs internet access to PyPI)
pip install -r requirements.txt

# 3. Create the local database
python manage.py migrate

# 4. (Optional) create an admin user for /admin/
python manage.py createsuperuser

# 5. Run the development server
python manage.py runserver
```

Then open http://127.0.0.1:8000/.

## Return-reminder "alarm"

In the UI, the dashboard and the **Loans → Overdue** tab surface books that
need to be asked back. To get a terminal/cron alarm:

```bash
python manage.py check_reminders            # overdue + due within 7 days
python manage.py check_reminders --within 3 # due within 3 days
```

Example crontab entry (daily at 9am, e-mail yourself the output):

```cron
0 9 * * * cd /path/to/bookfoil && .venv/bin/python manage.py check_reminders
```

## Project structure

```
bookfoil/
├── manage.py
├── requirements.txt
├── bookfoil/                 # project settings & URLs
└── library/                  # the app
    ├── models.py             # Shelf, Book, Bookmark, Borrow, WishlistItem
    ├── views.py              # CRUD + bookmark + borrow + wishlist
    ├── forms.py
    ├── urls.py
    ├── admin.py
    ├── management/commands/check_reminders.py
    └── templates/
```

## Data model

| Model          | Purpose                                                        |
|----------------|----------------------------------------------------------------|
| `Shelf`        | A storage location for physical books.                         |
| `Book`         | Core entity. Format (physical/digital), shelf, device, account.|
| `Bookmark`     | One per book — the page you stopped on.                        |
| `Borrow`       | A loan: borrower, dates, agreed return date, reminder flag.    |
| `WishlistItem` | A book you want but don't own yet.                             |
```
