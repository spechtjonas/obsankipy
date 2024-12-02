import logging
from typing import List

from anki.manager import (
    AnkiManager,
)
from config_parser import NewConfig
from notes.manager import set_new_ids
from notes.note import NoteType
from utils.helpers import open_cache, write_hashes_to_file
from vault import VaultManager

logger = logging.getLogger(__name__)


def run(config: NewConfig):
    vault_name = config.vault.dir_path.name
    hashes_path = config.hashes_cache_dir / f".{vault_name}_file_hashes.json"
    hashes = open_cache(hashes_path)
    note_types: List[NoteType] = config.get_note_types()
    anki_requester = AnkiManager(config.globals.anki.url)

    ids = anki_requester.get_ids()
    medias_in_anki = anki_requester.get_medias(config.globals.anki.fine_grained_image_search)
    pics_in_anki = medias_in_anki["images"]
    audios_in_anki = medias_in_anki["audios"]

    vault = VaultManager(
        config.vault.dir_path,
        config.vault.exclude_dirs_from_scan,
        config.vault.exclude_dotted_dirs_from_scan,
        config.vault.file_patterns_to_exclude,
        note_types,
    )

    vault.set_new_files(hashes)

    notes_manager = vault.get_notes_from_new_files()
    notes_manager.categorize_notes(ids)
    notes_manager.load_media_data(config.vault.medias_dir_path)
    notes_manager.categorize_medias(pics_in_anki, audios_in_anki)
    medias = notes_manager.get_media_to_add()

    notes_to_edit = notes_manager.get_all_notes_to_edit()
    notes_to_add = notes_manager.get_all_notes_to_add()
    notes_to_delete = notes_manager.get_all_notes_to_delete()

    # Remove notes from notes_to_edit which are part of notes_to_delete by file id
    notes_to_edit = [note for note in notes_to_edit if note.id not in {note.id for note in notes_to_delete}]

    decks_to_create = notes_manager.get_needed_target_decks()
    anki_requester.create_decks(decks_to_create)

    # Delete notes
    anki_requester.delete_notes(notes_to_delete)

    files_with_deleted_notes = notes_manager.get_files_with_deleted_notes()
    for file in files_with_deleted_notes:
        file.erase_deleted_ids_from_file_content()

    # Add new notes
    add_response = anki_requester.adds_new_notes(notes_to_add)  


    if add_response:
        set_new_ids(add_response)
        files_with_added_notes = notes_manager.get_files_with_added_notes()
        for file in files_with_added_notes:
            file.write_new_ids_to_file_content()

    # Update existing notes
    anki_requester.updates_existing_notes(notes_to_edit)

    # Rewrite updated files
    vault.write_updated_content_to_files()

    anki_requester.ensure_correct_deck(notes_to_edit)
    anki_requester.store_media_files(medias)

    curr_hashes = vault.get_curr_file_hashes()

    write_hashes_to_file(curr_hashes, hashes_path)

    # TODO need to change the Vault manager to manage IO operations with the files inside the vault
    # TODO need to error handle when we try to add a duplicate note
    # TODO create the cli using click
    # TODO create the tests
    # TODO better annotate python type annotations, like Any
    # TODO do logging
    # TODO what if someone deletes the ids in the obsidian note? we should be able to retrieve it back by using the findCards api, searching for the front field like this: *question*
    # TODO handle when the image referenced in the obsidian note is not in the same "case" as the file in the filesystem
    # TODO inline ids so we support lists as notes
    # TODO handle the delete path better..we might delete the structure of the note, which will stop being parsed and still want to delete it..
    # The request to delete notes is coupled with the Note object, and we should decouple it. The contents of the file will also be out of date after we delete a note it
    # and we need to update the contents to account for that
    # categorize medias maybe should get one whole type instead of 2, one for images and one for audios
