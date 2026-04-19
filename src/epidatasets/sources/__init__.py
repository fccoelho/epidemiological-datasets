"""Data source accessors for epidemiological datasets.

This module provides lazy-loading imports of all available data source
accessors.  Each accessor inherits from
:class:`~epidatasets._base.BaseAccessor` and can be discovered at runtime
via the plugin registry (:func:`~epidatasets.get_source`).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from epidatasets.sources.africa_cdc import AfricaCDCAccessor
    from epidatasets.sources.cdc_opendata import CDCOpenDataAccessor
    from epidatasets.sources.china_cdc import ChinaCDCAccessor
    from epidatasets.sources.colombia_ins import ColombiaINSAccessor
    from epidatasets.sources.copernicus_cds import CopernicusCDSAccessor
    from epidatasets.sources.datasus_pysus import DataSUSAccessor
    from epidatasets.sources.ecdc_opendata import ECDCOpenDataAccessor
    from epidatasets.sources.epipulse import EpiPulseAccessor
    from epidatasets.sources.eurostat import EurostatAccessor
    from epidatasets.sources.global_health import GlobalHealthAccessor
    from epidatasets.sources.healthdata_gov import HealthDataGovAccessor
    from epidatasets.sources.india_idsp import IndiaIDSPAccessor
    from epidatasets.sources.infodengue_api import InfoDengueAPI
    from epidatasets.sources.malaria_atlas import MalariaAtlasAccessor
    from epidatasets.sources.owid import OWIDAccessor
    from epidatasets.sources.paho import PAHOAccessor
    from epidatasets.sources.pathoplexus import PathoplexusAccessor
    from epidatasets.sources.respicast import RespiCastAccessor
    from epidatasets.sources.rki_germany import RKIGermanyAccessor
    from epidatasets.sources.ukhsa import UKHSAAccessor
    from epidatasets.sources.who_ghoclient import WHOAccessor

logger = logging.getLogger(__name__)

__all__ = [
    "AfricaCDCAccessor",
    "CDCOpenDataAccessor",
    "ChinaCDCAccessor",
    "ColombiaINSAccessor",
    "CopernicusCDSAccessor",
    "DataSUSAccessor",
    "ECDCOpenDataAccessor",
    "EpiPulseAccessor",
    "EurostatAccessor",
    "GlobalHealthAccessor",
    "HealthDataGovAccessor",
    "IndiaIDSPAccessor",
    "InfoDengueAPI",
    "MalariaAtlasAccessor",
    "OWIDAccessor",
    "PAHOAccessor",
    "PathoplexusAccessor",
    "RespiCastAccessor",
    "RKIGermanyAccessor",
    "UKHSAAccessor",
    "WHOAccessor",
]
