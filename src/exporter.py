"""Media Exporter"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Generator, Optional, Set

from anki.collection import Collection
from anki.decks import DeckId
from anki.utils import ids2str


class MediaExporter:
    "Deck Media Exporter"

    def __init__(self, col: Collection, did: DeckId | int):
        self.col = col
        self.did = did

    def get_filenames(self) -> Set[str]:
        "Get media filenames used in the deck that has the ID `self.did`"
        filenames = set()
        dids = self.col.decks.deck_and_child_ids(self.did)
        for flds, mid in self.col.db.all(
            f"select n.flds, n.mid from notes n, cards c where c.nid = n.id and c.did in {ids2str(dids)}"
        ):
            filenames.update(self.col.media.filesInStr(mid, flds))
        return filenames

    def export(
        self, folder: Path | str, exts: Optional[Set] = None
    ) -> Generator[str, None, None]:
        """
        Export media files in `self.did` to `folder`,
        including only files that has extensions in `exts` if `exts` is not None.
        Returns a generator that yields filenames as they are exported.
        """

        media_dir = self.col.media.dir()
        filenames = self.get_filenames()
        for filename in filenames:
            if exts is not None and os.path.splitext(filename)[1][1:] not in exts:
                continue
            src_path = os.path.join(media_dir, filename)
            dest_path = os.path.join(folder, filename)
            shutil.copyfile(src_path, dest_path)
            yield filename
