from pathlib import Path
from typing import List, Set, Dict, Tuple, Any, Union

from files import File
from media import MediaState, Picture, Audio
from notes.note import Note, State

import logging

logger = logging.getLogger(__name__)


class NotesManager:
    """
    will handle a list of Notes, on what has to be done with each of them, either add, edit or delete
    """

    notes: List[Note]
    notes_to_add: List[Note]
    notes_to_edit: List[Note]
    notes_to_delete: List[Note]
    new_medias: List[Any]
    medias: List[Picture]

    def __init__(self, notes) -> None:
        self.notes: List[Note] = notes
        self.notes_to_add: List[Note] = list()
        self.notes_to_edit: List[Note] = list()
        self.notes_to_delete: List[Note] = list()
        self.new_medias: List[Picture] = list()
        self.new_audios: List[Audio] = list()
        self.medias: List[Any] = [picture for note in notes for picture in note.medias]

    def parse_note_to_add(self, note: Note) -> None:
        self.notes_to_add.append(note)

    def parse_note_to_edit(self, note: Note) -> None:
        self.notes_to_edit.append(note)

    def parse_note_to_delete(self, note: Note) -> None:
        self.notes_to_delete.append(note)

    def get_all_notes(self) -> List[Note]:
        return self.notes

    def get_all_notes_to_add(self) -> List[Note]:
        return self.notes_to_add

    def get_all_notes_to_edit(self) -> List[Note]:
        return self.notes_to_edit

    def get_all_notes_to_delete(self) -> List[Note]:
        return self.notes_to_delete

    def categorize_notes(self, existent_ids: Set[int]) -> None:
        """
        2 side effects outside the scope of the class:
            mutates the notes state to either NEW, EXISTING or DELETED
            call create_source_files_add_notes_metadata to mutate the source files
        """
        for note in self.notes:
            if note.state == State.MARKED_FOR_DELETION:
                self.parse_note_to_delete(note)
            elif note.state == State.UNKNOWN and note.id in existent_ids:
                note.set_state(State.EXISTING)
                self.parse_note_to_edit(note)
            else:  # note is new
                note.set_state(State.NEW)
                self.parse_note_to_add(note)

        self.create_source_files_add_notes_metadata()

    def get_needed_target_decks(self):
        return set([note.target_deck for note in self.notes])

    def create_source_files_add_notes_metadata(self) -> None:
        """
        mutates the source files of each note:
        - to add the notes attribute

        It is helpful later so we can have a mapping of files that have to be updated with the ID and its new notes
        """
        for note in self.notes_to_add:
            note.source_file.append_to_add_notes(note)

    def categorize_medias(self, pictures_in_anki: Union[Dict[str, str], Set[str]],
                              audios_in_anki: Union[Dict[str, str], Set[str]]) -> None:
        """
        analyzes the name of the medias as well as the content of the picture to determine if it is new or not
        """
        # if pictures_in_anki and audios_in_anki are a set, it means that the user has chosen to not compare the content of the media
        if isinstance(pictures_in_anki, set) and isinstance(audios_in_anki, set):
            medias_in_anki = pictures_in_anki.union(audios_in_anki)
            for media in self.medias:
                if media.filename in medias_in_anki:
                    media.set_state(MediaState.STORED)
                else:
                    media.set_state(MediaState.NEW)
                    self.new_medias.append(media)
        else:
            medias_in_anki = {**pictures_in_anki, **audios_in_anki}
            for media in self.medias:
                if (
                    media.filename in medias_in_anki
                    and media.data == medias_in_anki[media.filename]
                ):
                    media.set_state(MediaState.STORED)
                else:
                    media.set_state(MediaState.NEW)
                    self.new_medias.append(media)

    def load_media_data(self, path_to_directory: Path) -> None:
        """ """
        for media in self.medias:
            media.load_data(Path(path_to_directory))

    def get_media_to_add(self) -> List[Picture]:
        return self.new_medias
    
    def get_files_with_deleted_notes(self) -> Set[File]:
        return set([note.source_file for note in self.notes_to_delete])

    def get_files_with_added_notes(self) -> Set["File"]:
        return set([note.source_file for note in self.notes_to_add])


def set_new_ids(ids: List[Tuple[Note, int]]) -> None:
    for note, id in ids:
        note.id = id
        note.set_state(State.EXISTING)
