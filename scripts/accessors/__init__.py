"""
Epidemiological data accessors.

This package provides standardized access to various epidemiological datasets
from around the world.

Key accessors:
- WHOAccessor: Uses ghoclient library for WHO GHO data
- DataSUSAccessor: Uses PySUS library for Brazilian health data
- PAHOAccessor: For PAHO (Pan American Health Organization) data
- EurostatAccessor: For Eurostat (EU) health statistics
- CDCAccessor: For US CDC data (planned)
- ECDCAccessor: For European CDC data (planned)

For more information:
- ghoclient: https://pypi.org/project/ghoclient/
- PySUS: https://pypi.org/project/pysus/
- eurostat: https://pypi.org/project/eurostat/
"""

# Use ghoclient-based WHO accessor
try:
    from .who_ghoclient import WHOAccessor

    WHO_AVAILABLE = True
except ImportError:
    WHO_AVAILABLE = False

# Use PySUS-based DATASUS accessor
try:
    from .datasus_pysus import DataSUSAccessor

    DATASUS_AVAILABLE = True
except ImportError:
    DATASUS_AVAILABLE = False

# PAHO accessor (no external dependencies)
try:
    from .paho import PAHOAccessor

    PAHO_AVAILABLE = True
except ImportError:
    PAHO_AVAILABLE = False

# Eurostat accessor (requests library only - standard)
try:
    from .eurostat import EurostatAccessor

    EUROSTAT_AVAILABLE = True
except ImportError:
    EUROSTAT_AVAILABLE = False

# OWID accessor (requests library only - standard)
try:
    from .owid import OWIDAccessor

    OWID_AVAILABLE = True
except ImportError:
    OWID_AVAILABLE = False

# Other accessors (to be implemented)
# from .cdc import CDCAccessor
# from .ecdc import ECDCAccessor

__all__ = []

if WHO_AVAILABLE:
    __all__.append("WHOAccessor")
else:
    import warnings

    warnings.warn(
        "WHOAccessor not available. Install ghoclient: pip install ghoclient",
        ImportWarning,
    )

if DATASUS_AVAILABLE:
    __all__.append("DataSUSAccessor")
else:
    import warnings

    warnings.warn(
        "DataSUSAccessor not available. Install PySUS: pip install pysus", ImportWarning
    )

if PAHO_AVAILABLE:
    __all__.append("PAHOAccessor")

if EUROSTAT_AVAILABLE:
    __all__.append("EurostatAccessor")

if OWID_AVAILABLE:
    __all__.append("OWIDAccessor")

__version__ = "0.1.0"

# Metadata about available libraries
LIBRARY_INFO = {
    "ghoclient": {
        "description": "WHO Global Health Observatory client",
        "url": "https://pypi.org/project/ghoclient/",
        "available": WHO_AVAILABLE,
    },
    "pysus": {
        "description": "Brazilian health data (DATASUS) access",
        "url": "https://pypi.org/project/pysus/",
        "available": DATASUS_AVAILABLE,
    },
    "paho": {
        "description": "PAHO (Pan American Health Organization) data access",
        "url": "https://www.paho.org/en/data",
        "available": PAHO_AVAILABLE,
    },
    "eurostat": {
        "description": "Eurostat (EU) health statistics access",
        "url": "https://pypi.org/project/eurostat/",
        "available": EUROSTAT_AVAILABLE,
    },
    "owid": {
        "description": "Our World in Data health statistics access",
        "url": "https://ourworldindata.org/",
        "available": OWID_AVAILABLE,
    },
}


def check_libraries():
    """
    Check which libraries are installed and available.

    Returns
    -------
        Dictionary with library availability status
    """
    return LIBRARY_INFO.copy()


def print_status():
    """Print status of available libraries."""
    print("Epidemiological Data Accessors - Status")
    print("=" * 50)

    for lib, info in LIBRARY_INFO.items():
        status = "✅ Available" if info["available"] else "❌ Not installed"
        print(f"\n{lib}:")
        print(f"  Status: {status}")
        print(f"  Description: {info['description']}")
        print(f"  URL: {info['url']}")

    print("\n" + "=" * 50)
    print("To install missing libraries:")
    if not WHO_AVAILABLE:
        print("  pip install ghoclient")
    if not DATASUS_AVAILABLE:
        print("  pip install pysus")
    if not EUROSTAT_AVAILABLE:
        print("  pip install eurostat")
