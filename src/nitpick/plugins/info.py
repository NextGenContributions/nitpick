"""Info needed by the plugins."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

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
    def create(cls, project: Project, path_from_root: str) -> FileInfo:
        """Clean the file name and get its tags."""
        if Deprecation.pre_commit_without_dash(path_from_root):
            clean_path = DOT + path_from_root
        else:
            clean_path = DOT + path_from_root[1:] if path_from_root.startswith("-") else path_from_root
        tags = FileInfo.tags_from_filename(clean_path)
        return cls(project, clean_path, tags)

    @staticmethod
    def tags_from_filename(path: str) -> set[str]:
        """Get a list of tags associated with the file."""
        tags = identify.tags_from_filename(path)

        # Check for conflicting tags, there can be only one of them
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
