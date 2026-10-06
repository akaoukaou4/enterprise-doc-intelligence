"""Data structures shared by the document pipeline.

A Chunk is plain Python data. It knows nothing about Docling, FastAPI, Airflow
or the database, so every pipeline stage can create, test and pass it around.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    """One piece of a document, with the provenance needed for citations."""

    text: str
    page_numbers: list[int]  # a chunk can span pages, e.g. [2, 3]
    heading: str | None  # nearest section heading, if Docling found one
