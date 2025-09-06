"""Custom exceptions for pyflip."""

from __future__ import annotations


class PyflipError(Exception):
    """Base exception for pyflip errors."""


class URLSanitizationError(PyflipError):
    """Raised when the input URL cannot be sanitized."""
    pass


class DownloadError(PyflipError):
    """Raised for network/download issues (e.g., non-200, connection)."""
    pass


class ParseError(PyflipError):
    """Raised when parsing config.js fails or data is invalid."""
    pass


class FileSystemError(PyflipError):
    """Raised for local filesystem failures (create, write, remove)."""
    pass


class PDFCreationError(PyflipError):
    """Raised when creating the final PDF fails."""
    pass


__all__ = [
    "PyflipError",
    "URLSanitizationError",
    "DownloadError",
    "ParseError",
    "FileSystemError",
    "PDFCreationError",
]

