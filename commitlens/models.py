from dataclasses import dataclass


@dataclass(frozen=True)
class Commit:
    sha: str
    message: str
    author: str
    date: str
