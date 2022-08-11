"""
Initialize the add-on, and adds a menu item under the gears icon in the deck list screen
to export media from a target deck.
"""

import os
from concurrent.futures import Future
from pathlib import Path
from typing import List, Optional

import aqt
from anki.decks import DeckId
from aqt import gui_hooks, mw
from aqt.qt import *
from aqt.utils import getText, showInfo, tooltip

from .api_key import get_google_api_key
from .exporter import DeckMediaExporter
from .pathlike.errors import PathLikeError

os.environ["GOOGLE_API_KEY"] = get_google_api_key()
from .pathlike.gdrive import GDriveRoot

ADDON_NAME = "Media Exporter"
ADDON_DIR = os.path.dirname(__file__)
AUDIO_EXTS = aqt.editor.audio


def get_export_folder() -> Path:
    "Get the export folder from the user."
    return Path(
        QFileDialog.getExistingDirectory(
            mw, caption="Choose the folder where you want to export the files to"
        )
    )


def on_deck_browser_will_show_options_menu(menu: QMenu, did: int) -> None:
    """Adds a menu item under the gears icon to export a deck's media files."""

    def export_media(exclude_files: Optional[List[str]] = None) -> None:
        folder = get_export_folder()
        config = mw.addonManager.getConfig(__name__)
        exts = set(AUDIO_EXTS) if config.get("audio_only", False) else None
        field = config.get("search_in_field", None)
        want_cancel = False

        def export_task() -> int:
            exporter = DeckMediaExporter(
                mw.col, DeckId(did), field, exclude_files=exclude_files
            )
            note_count = mw.col.decks.card_count([DeckId(did)], include_subdecks=True)
            progress_step = min(2500, max(2500, note_count))
            media_i = 0
            for notes_i, (media_i, _) in enumerate(exporter.export(folder, exts)):
                if notes_i % progress_step == 0:
                    mw.taskman.run_on_main(
                        lambda notes_i=notes_i + 1, media_i=media_i: update_progress(  # type: ignore
                            notes_i, note_count, media_i
                        )
                    )
                    if want_cancel:
                        break
            return media_i

        def update_progress(notes_i: int, note_count: int, media_i: int) -> None:
            nonlocal want_cancel
            mw.progress.update(
                label=f"Processed {notes_i} notes and exported {media_i} files",
                max=note_count,
                value=notes_i,
            )
            want_cancel = mw.progress.want_cancel()

        def on_done(future: Future) -> None:
            try:
                count = future.result()
            finally:
                mw.progress.finish()
            tooltip(f"Exported {count} media files", parent=mw)

        mw.progress.start(label="Exporting media...", parent=mw)
        mw.progress.set_title(ADDON_NAME)
        mw.taskman.run_in_background(export_task, on_done=on_done)

    action_basic = menu.addAction("Export Media")
    action_gdrive = menu.addAction("Export Media (exclude files in GDrive)")
    qconnect(action_basic.triggered, export_media)

    def export_media_excluding_gdrive_files() -> None:
        url, succeded = getText("Enter the path to the GDrive folder")
        if not succeded:
            return

        try:
            file_names_in_gdrive = [
                file.name for file in GDriveRoot(url).list_files(recursive=True)
            ]
        except PathLikeError as e:
            showInfo(str(e))
            return

        export_media(exclude_files=file_names_in_gdrive)

    qconnect(action_gdrive.triggered, export_media_excluding_gdrive_files)


gui_hooks.deck_browser_will_show_options_menu.append(
    on_deck_browser_will_show_options_menu
)
