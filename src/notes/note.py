import enum
import re
from typing import List, Optional, Any

from notes.fields import (
    NoteField,
    FrontField,
    BackField,
    CustomField,
    ContextField,
    LinkField,
)
from media import Picture, Audio
from utils.helpers import convert_listDicts_to_dict
from utils.patterns import (
    IMAGE_FILE_WIKILINK_REGEX,
    AUDIO_FILE_REGEX,
    IMAGE_FILE_MARKDOWN_REGEX,
)

from urllib.parse import unquote


class State(enum.Enum):
    EXISTING = enum.auto()
    UNKNOWN = enum.auto()
    NEW = enum.auto()
    MARKED_FOR_DELETION = enum.auto()


# interface of Field using Protocol


class DuplicateScopeOptions:
    deck_name: str
    check_children: bool
    check_all_models: bool


class NoteOptions:
    allow_duplicate: bool
    duplicate_scope: str
    duplicate_scope_options: DuplicateScopeOptions


class Note:
    state: State
    note_type: Any
    id: Optional[int]
    source_file: "File"
    note_start_span: int
    note_end_span: int
    original_note_text: str
    target_deck: str
    tags: List[str]
    fields: List[NoteField]  # implements the interface of NoteField
    medias: List[Any]
    to_delete: bool
    options: NoteOptions
    file_note_metadata: "FileNoteMetadata"
    id_location_in_file: int

    def __init__(
        self,
        note_match,
        source_file,
        target_deck,
        note_type,
        file_note_metadata
    ):
        """
        based on the match, source file, target deck and note type
        we should get all the other attributes
        """
        self.note_type = note_type
        self.note_match = note_match
        self.file_note_metadata = file_note_metadata
        self.original_note_text = note_match.group(0)

        named_captures = note_match.groupdict()
        self.check_state(named_captures)

        self.source_file = source_file
        self.note_start_span = note_match.start()
        self.note_end_span = note_match.end()
        self.curr_note_text = self.original_note_text
        self.target_deck = target_deck
        self.tags = self.file_note_metadata.tags

        self.medias = list()
        self.audios = list()
        self.find_medias()
        self.create_fields()
        self.set_id_location_in_file()

        self.options = NoteOptions()


    def check_state(self, named_captures):
        if named_captures["delete"] is not None:
            self.state = State.MARKED_FOR_DELETION
            self.id = int(named_captures["id_num"])
        elif named_captures["id_num"] is not None:
            self.state = (
                State.UNKNOWN
            )  # this id may exist in anki, we need to check later
            self.id = int(named_captures["id_num"])
        else:
            self.state = State.NEW
            self.id = None

    # def set_id_location_in_file(self):
    #     if self.note_type.note_type == NoteVariant.CLOZE:
    #         self.id_location_in_file = self.note_match.end(
    #             1
    #         )  # because there is no back field
    #     else:
    #         self.id_location_in_file = self.note_match.end(2)

    def set_id_location_in_file(self):
        """Get position after last line of matched note"""
        match_end = self.note_match.end(0)
        match_text = self.note_match.group(0)

        # If match does end with newline, go back one position to avoid inserting another newline
        self.id_location_in_file = match_end
        text = match_text
        while text.endswith("\n"):
            self.id_location_in_file -= 1
            text = text[:-1]
            

    def find_medias(self):
        for match in IMAGE_FILE_WIKILINK_REGEX.finditer(self.original_note_text):
            full_file_name = f"{match.group('filename')}.{match.group('extension')}"
            pic = Picture(filename=full_file_name)
            self.medias.append(pic)
        for match in IMAGE_FILE_MARKDOWN_REGEX.finditer(self.original_note_text):
            full_file_name = unquote(
                f"{match.group('filename')}.{match.group('extension')}"
            )
            pic = Picture(filename=full_file_name)
            self.medias.append(pic)
        for match in AUDIO_FILE_REGEX.finditer(self.original_note_text):
            full_file_name = f"{match.group('filename')}.{match.group('extension')}"
            audio = Audio(filename=full_file_name)
            self.medias.append(audio)

    def set_state(self, state):
        self.state = state

    def create_fields(self):
        if (
            self.note_type.note_type == NoteVariant.BASIC
            or self.note_type.note_type == NoteVariant.BASIC_AND_REVERSED_CARD
            or self.note_type.note_type == NoteVariant.BASIC_TYPE_ANSWER
        ):
            vault_name = self.source_file.file_note_metadata.vault_name
            file_name = self.source_file.file_name
            self.fields = [
                FrontField(self.note_match.group(1), vault_name, file_name),
                BackField(self.note_match.group(2), vault_name),
            ]
        elif self.note_type.note_type == NoteVariant.CLOZE:
            vault_name = self.source_file.file_note_metadata.vault_name
            file_name = self.source_file.file_name
            # use the FrontField because the transformations will be the same, just change the field name
            self.fields = [
                FrontField(
                    self.note_match.group(1), vault_name, file_name, field_name="Text"
                )
            ]

        elif self.note_type.note_type == NoteVariant.OBSIDIAN:

            vault_name = self.source_file.file_note_metadata.vault_name
            file_name = self.source_file.file_name

            self.fields = []

            for field_name, value in self.note_type.fields.items():
                if isinstance(value, int):
                    # Use integer value as match group index
                    field_text = self.note_match.group(value)
                    field = CustomField(field_text, vault_name, field_name)
                    self.fields.append(field)
                elif value == "CONTEXT":
                    relative_path = self.source_file.relative_path
                    file_text = self.source_file.curr_file_content
                    note_hierarchy = self.get_heading_hierarchy(file_text, self.note_start_span)

                    field = ContextField(relative_path, note_hierarchy, field_name)
                    self.fields.append(field)

                elif value == "LINK":
                    field = LinkField(file_name, vault_name, field_name)
                    self.fields.append(field)

        for field in self.fields:
            field.transform()

    def to_anki_dict(self):
        if self.state == State.NEW:  # to be used with addNote in anki
            return {
                "modelName": self.note_type.to_anki_dict(),
                "deckName": self.target_deck,
                "tags": self.tags,
                "fields": {
                    field.get_field_name(): field.get_field_value()
                    for field in self.fields
                },
            }
        else:  # to be used with updateNote in anki
            return {
                "id": self.id,
                "modelName": self.note_type.to_anki_dict(),
                "deckName": self.target_deck,
                "tags": self.tags,
                "fields": {
                    field.get_field_name(): field.get_field_value()
                    for field in self.fields
                },
            }
        
    def get_heading_hierarchy(self, text, position):
        # Regex pattern to match Markdown headings (ATX style)
        heading_regex = re.compile(r'^(#{1,6})\s+(.*)', re.MULTILINE)
        
        # Find all headings in the markdown text
        headings = []
        for match in heading_regex.finditer(text):
            level = len(match.group(1))  # Number of '#' symbols indicates the level
            heading_text = match.group(2).strip()
            start_pos = match.start()
            
            # Store heading details
            headings.append({
                'level': level,
                'text': heading_text,
                'position': start_pos
            })
        
        # Initialize hierarchy
        hierarchy = []
        current_level_headings = {}
        
        # Process headings up to the given position
        for heading in headings:
            if heading['position'] > position:
                break  # We've passed the position; stop processing
            
            level = heading['level']
            text = heading['text']
            
            # Update current level headings
            current_level_headings[level] = text
            
            # Remove deeper levels
            keys_to_remove = [lvl for lvl in current_level_headings if lvl > level]
            for key in keys_to_remove:
                del current_level_headings[key]
            
            # Build hierarchy
            hierarchy = [current_level_headings[lvl] for lvl in sorted(current_level_headings)]
        
        return hierarchy


class NoteVariant(enum.Enum):
    BASIC = enum.auto()
    CLOZE = enum.auto()
    BASIC_AND_REVERSED_CARD = enum.auto()
    BASIC_TYPE_ANSWER = enum.auto()
    OBSIDIAN = enum.auto()

    def get_string(self):
        mapping = {
            NoteVariant.BASIC: "Basic",
            NoteVariant.CLOZE: "Cloze",
            NoteVariant.BASIC_AND_REVERSED_CARD: "Basic (and reversed card)",
            NoteVariant.BASIC_TYPE_ANSWER: "Basic (type in the answer)",
            NoteVariant.OBSIDIAN: "Obsidian",
        }
        return mapping.get(self)


class NoteType:
    name: str
    regexes: List[str]
    fields: List[dict]

    def __init__(self, note_variant: NoteVariant, note_type: dict):
        self.note_type = note_variant
        self.name = note_variant.get_string()
        self.regexes = note_type["regexes"]

        fields = note_type["fields"]

        if isinstance(fields, dict):
            self.fields = fields
        elif isinstance(fields, list):
            self.fields = convert_listDicts_to_dict(fields)
        else:
            raise ValueError("Config entry for fields must be dict or list of dicts")

    def to_anki_dict(self):
        return self.name

    def __str__(self):
        return f"{self.name} with the regexes: {self.regexes}"
