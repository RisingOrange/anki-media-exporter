from aqt import gui_hooks
from aqt.qt import QMenu
from aqt.qt import QMenu, qconnect

from .utils import export_media, export_media_excluding_gdrive_files


def on_deck_browser_will_show_options_menu(menu: QMenu, did: int) -> None:
    """Adds a menu item under the gears icon to export a deck's media files."""

    action_basic = menu.addAction("Export Media")
    qconnect(action_basic.triggered, lambda: export_media(did))

    action_gdrive = menu.addAction("Export Media (exclude files in GDrive)")
    qconnect(action_gdrive.triggered, lambda: export_media_excluding_gdrive_files(did))


def setup_deck_browser() -> None:
    gui_hooks.deck_browser_will_show_options_menu.append(
        on_deck_browser_will_show_options_menu
    )
