import logging
from pathlib import Path
from typing import List, Optional

import os

from ankimd.notes.note import NoteType, NoteVariant

logger = logging.getLogger(__name__)


from typing_extensions import Annotated
from pydantic import BaseModel, field_validator, ValidationInfo, Field


class AnkiConfig(BaseModel):
    url: str
    deck_name: Optional[str] = "Default"
    tags: Optional[List[str]] = []
    fine_grained_image_search: Optional[bool] = False


class VaultConfig(BaseModel):
    dir_path: str
    medias_dir_path: str
    exclude_dirs_from_scan: Optional[List[str]] = []
    exclude_dotted_dirs_from_scan: Optional[bool] = True
    file_patterns_to_exclude: Optional[List[str]] = []

    @field_validator("dir_path", "medias_dir_path")
    def dir_path_must_exist(cls, v):
        if not os.path.exists(v):
            raise ValueError(f"Path {v} does not exist")
        return Path(v)

# class RegexConfig(BaseModel):
#     basic: Optional[List[str]] = []
#     basic_reversed: Optional[List[str]] = []
#     type_answer: Optional[List[str]] = []
#     cloze: Optional[List[str]] = []
#     obsidian: Optional[List[str]] = []

#     def get_note_types(self):
#         note_types = []
#         if self.basic:
#             note_types.append(
#                 NoteType(
#                     regexes=self.basic,
#                     note_variant=NoteVariant.BASIC,
#                 )
#             )
#         if self.basic_reversed:
#             note_types.append(
#                 NoteType(
#                     regexes=self.basic_reversed,
#                     note_variant=NoteVariant.BASIC_AND_REVERSED_CARD,
#                 )
#             )
#         if self.type_answer:
#             note_types.append(
#                 NoteType(
#                     regexes=self.type_answer,
#                     note_variant=NoteVariant.BASIC_TYPE_ANSWER,
#                 )
#             )
#         if self.cloze:
#             note_types.append(
#                 NoteType(
#                     regexes=self.cloze,
#                     note_variant=NoteVariant.CLOZE,
#                 )
#             )
#         if self.obsidian:
#             note_types.append(
#                 NoteType(
#                     regexes=self.obsidian,
#                     note_variant=NoteVariant.OBSIDIAN,
#                 )
#             )
#         return note_types

class NotetypeConfig(BaseModel):
    Basic: Optional[dict] = {}
    basic_reversed: Optional[dict] = {}
    type_answer: Optional[dict] = {}
    cloze: Optional[dict] = {}
    Obsidian: Optional[dict] = {}
    Altklausuren: Optional[dict] = {}

    def get_note_types(self):
        note_types = []
        if self.Basic:
            note_types.append(
                NoteType(
                    note_type=self.Basic,
                    note_variant=NoteVariant.BASIC,
                )
            )
        # if self.basic_reversed:
        #     note_types.append(
        #         NoteType(
        #             regexes=self.basic_reversed,
        #             note_variant=NoteVariant.BASIC_AND_REVERSED_CARD,
        #         )
        #     )
        # if self.type_answer:
        #     note_types.append(
        #         NoteType(
        #             regexes=self.type_answer,
        #             note_variant=NoteVariant.BASIC_TYPE_ANSWER,
        #         )
        #     )
        # if self.cloze:
        #     note_types.append(
        #         NoteType(
        #             regexes=self.cloze,
        #             note_variant=NoteVariant.CLOZE,
        #         )
        #     )
        if self.Obsidian:
            note_types.append(
                NoteType(
                    note_type=self.Obsidian,
                    note_variant=NoteVariant.OBSIDIAN,
                )
            )
        if self.Altklausuren:
            note_types.append(
                NoteType(
                    note_type=self.Altklausuren,
                    note_variant=NoteVariant.ALTKLAUSUREN,
                )
            )
        return note_types


class GlobalConfig(BaseModel):
    anki: AnkiConfig


class NewConfig(BaseModel):
    globals: GlobalConfig
    vault: VaultConfig
    notetypes: NotetypeConfig
    hashes_cache_dir: Annotated[str, Field(validate_default=True)] = ""

    def get_note_types(self):
        return self.notetypes.get_note_types()

    @field_validator("hashes_cache_dir", mode="after")
    def normalize_hashes_cache_dir(cls, v, info: ValidationInfo):
        """Normalize the hashes cache directory path, but don't require it to exist."""
        if v:
            path = Path(v)
            # Don't validate existence - the directory will be created if needed
            return path
        else:
            # Default to .obsankipy in the vault directory
            return Path(info.data["vault"].dir_path) / ".obsankipy"

    @staticmethod
    def _normalize_path(raw: str | None, base_dir: Path) -> str | None:
        if raw is None:
            return None
        path = Path(raw)
        if path.is_absolute():
            return str(path)
        # Resolve relative paths against base_dir
        normalized_path = (base_dir / path).resolve()
        return str(normalized_path)

    @classmethod
    def from_dict(cls, data: dict, *, base_dir: Path) -> "NewConfig":
        data = data.copy()

        vault_cfg = data.get("vault")
        if isinstance(vault_cfg, dict):
            for key in ("dir_path", "medias_dir_path"):
                if key in vault_cfg:
                    vault_cfg[key] = cls._normalize_path(vault_cfg[key], base_dir)

        if "hashes_cache_dir" in data and data["hashes_cache_dir"]:
            data["hashes_cache_dir"] = cls._normalize_path(data["hashes_cache_dir"], base_dir)

        return cls(**data)
