import os
from concurrent.futures import Future
from pathlib import Path
from typing import List, Optional

from anki.decks import DeckId
from aqt import mw
from aqt.qt import *
from aqt.utils import getText, showInfo, tooltip

from .api_key import get_google_api_key
from .constants import AUDIO_EXTS, ADDON_NAME
from .exporter import DeckMediaExporter
from .pathlike.errors import PathLikeError

os.environ["GOOGLE_API_KEY"] = get_google_api_key()
from .pathlike.gdrive import GDriveRoot


def get_export_folder() -> str:
    "Get the export folder from the user."
    return QFileDialog.getExistingDirectory(
        mw, caption="Choose the folder where you want to export the files to"
    )


def export_media_excluding_gdrive_files(did: int) -> None:
    url, succeded = getText("Enter the path to the GDrive folder")
    if not succeded:
        return

    want_cancel = False

    def get_gdrive_file_list(url: str) -> List[str]:
        result: List[str] = []

        progress_step = 100
        ctr = 0
        for file in GDriveRoot(url).list_files(recursive=True):
            if mw.progress.want_cancel():
                nonlocal want_cancel
                want_cancel = True
                return []

            ctr += 1
            if ctr % progress_step == 0:
                mw.taskman.run_on_main(
                    lambda ctr=ctr: mw.progress.update(  # type: ignore
                        label=(
                            "Looking up files in Google drive...<br>"
                            f"Found {ctr} files..."
                        )
                    )
                )

            result.append(file.name)
        return result

    def on_done(future: Future) -> None:
        try:
            file_names_in_gdrive = future.result()
        except PathLikeError as e:
            showInfo(str(e))
            return

        if want_cancel:
            tooltip("Cancelled Media Export.")
            return

        export_media(did=did, exclude_files=file_names_in_gdrive)

    mw.taskman.with_progress(
        label="Looking up files in Google drive...",
        task=lambda: get_gdrive_file_list(url),
        on_done=on_done,
    )


def export_media(did: int, exclude_files: Optional[List[str]] = None) -> None:
    export_path = get_export_folder()
    if not export_path:
        tooltip("Cancelled Media Export.")
        return

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
        for notes_i, (media_i, _) in enumerate(
            exporter.export(Path(export_path), exts)
        ):
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