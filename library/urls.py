"""URL routes for the library app."""

from django.urls import path

from . import views

app_name = "library"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),

    # Books (CRUD)
    path("books/", views.book_list, name="book_list"),
    path("books/add/", views.book_create, name="book_create"),
    path("books/<int:pk>/", views.book_detail, name="book_detail"),
    path("books/<int:pk>/edit/", views.book_update, name="book_update"),
    path("books/<int:pk>/delete/", views.book_delete, name="book_delete"),

    # Bookmark
    path(
        "books/<int:pk>/bookmark/",
        views.bookmark_edit,
        name="bookmark_edit",
    ),

    # Borrowing
    path(
        "books/<int:pk>/borrow/",
        views.borrow_create,
        name="borrow_create",
    ),
    path("borrows/", views.borrow_list, name="borrow_list"),
    path(
        "borrows/<int:pk>/return/",
        views.borrow_return,
        name="borrow_return",
    ),

    # Shelves
    path("shelves/", views.shelf_list, name="shelf_list"),
    path("shelves/add/", views.shelf_create, name="shelf_create"),
    path("shelves/<int:pk>/edit/", views.shelf_update, name="shelf_update"),
    path(
        "shelves/<int:pk>/delete/",
        views.shelf_delete,
        name="shelf_delete",
    ),

    # Wishlist
    path("wishlist/", views.wishlist, name="wishlist"),
    path("wishlist/add/", views.wishlist_create, name="wishlist_create"),
    path(
        "wishlist/<int:pk>/edit/",
        views.wishlist_update,
        name="wishlist_update",
    ),
    path(
        "wishlist/<int:pk>/toggle/",
        views.wishlist_toggle_acquired,
        name="wishlist_toggle",
    ),
    path(
        "wishlist/<int:pk>/delete/",
        views.wishlist_delete,
        name="wishlist_delete",
    ),
]
