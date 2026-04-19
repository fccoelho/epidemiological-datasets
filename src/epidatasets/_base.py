from abc import ABC, abstractmethod
from typing import Any, ClassVar

import pandas as pd


class BaseAccessor(ABC):
    """Abstract base class for epidemiological data accessors.

    All data source accessors must inherit from this class and implement
    at minimum the ``list_countries`` method.

    Attributes
    ----------
    source_name : str
        Short identifier for the data source (e.g. ``"who"``, ``"paho"``).
    source_description : str
        Human-readable description of the data source.
    source_url : str
        URL of the original data source.
    """

    source_name: ClassVar[str] = ""
    source_description: ClassVar[str] = ""
    source_url: ClassVar[str] = ""

    @abstractmethod
    def list_countries(self) -> pd.DataFrame:
        """Return a DataFrame of countries covered by this source.

        Returns
        -------
        pd.DataFrame
            At minimum columns ``country_code`` and ``country_name``.
        """

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(source={self.source_name!r})"

    def __str__(self) -> str:
        return f"{self.source_description} ({self.source_url})"

    def info(self) -> dict[str, Any]:
        """Return a dictionary of metadata about this source."""
        return {
            "name": self.source_name,
            "description": self.source_description,
            "url": self.source_url,
            "class": self.__class__.__name__,
        }
