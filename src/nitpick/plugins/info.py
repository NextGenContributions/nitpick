"""Info needed by the plugins."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

from identify import identify
from loguru import logger

from nitpick.constants import DOT
from nitpick.exceptions import Deprecation

CONFLICTING_TAGS = {"ini", "toml", "yaml", "json"}

if TYPE_CHECKING:
    from nitpick.core import Project


@dataclass
class FileInfo:
    """File information needed by the plugin."""

    project: Project
    path_from_root: str
    tags: set[str] = field(default_factory=set)

    @classmethod
    def create(cls, project: Project, path_from_root: str, tags: Iterable[str] | None = None) -> FileInfo:
        """Clean the file name and get its tags."""
        if Deprecation.pre_commit_without_dash(path_from_root):
            clean_path = DOT + path_from_root
        else:
            clean_path = DOT + path_from_root[1:] if path_from_root.startswith("-") else path_from_root

        if not tags:
            # Auto-detect a list of tags associated with the file
            tags = identify.tags_from_filename(clean_path)

        tags = FileInfo.remove_conflicting_tags(clean_path, tags)
        return cls(project, clean_path, tags)

    @staticmethod
    def remove_conflicting_tags(path: str, input_tags: Iterable[str] | None) -> set[str]:
        """Check and remove conflicting tags, there can be only one of them."""
        if not input_tags:
            return set()

        tags = set(input_tags)
        found_tags = CONFLICTING_TAGS.intersection(tags)
        if len(found_tags) > 1 and (ext := Path(path).suffix):
            # The file has a valid extension and not just some ".dotfile"
            ext = ext[1:].lower()
            logger.info(f"Found conflicting tags {found_tags} for file at {path}")
            if ext in found_tags:
                logger.info(f"Keeping '{ext}' tag as it matches the extension")
                # Keep only the tag that matches the extension
                tags -= found_tags
                tags.add(ext)

        # If there's no conflict or the extension is not recognized, return all the tags
        return tags
