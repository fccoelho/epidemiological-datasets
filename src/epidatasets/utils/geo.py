"""Geographic utilities for country code handling."""

from __future__ import annotations

ISO2_TO_ISO3: dict[str, str] = {
    "AF": "AFG", "AL": "ALB", "DZ": "DZA", "AD": "AND", "AO": "AGO",
    "AG": "ATG", "AR": "ARG", "AM": "ARM", "AU": "AUS", "AT": "AUT",
    "AZ": "AZE", "BS": "BHS", "BH": "BHR", "BD": "BGD", "BB": "BRB",
    "BY": "BLR", "BE": "BEL", "BZ": "BLZ", "BJ": "BEN", "BT": "BTN",
    "BO": "BOL", "BA": "BIH", "BW": "BWA", "BR": "BRA", "BN": "BRN",
    "BG": "BGR", "BF": "BFA", "BI": "BDI", "KH": "KHM", "CM": "CMR",
    "CA": "CAN", "CV": "CPV", "CF": "CAF", "TD": "TCD", "CL": "CHL",
    "CN": "CHN", "CO": "COL", "KM": "COM", "CG": "COG", "CD": "COD",
    "CR": "CRI", "CI": "CIV", "HR": "HRV", "CU": "CUB", "CY": "CYP",
    "CZ": "CZE", "DK": "DNK", "DJ": "DJI", "DM": "DMA", "DO": "DOM",
    "EC": "ECU", "EG": "EGY", "SV": "SLV", "GQ": "GNQ", "ER": "ERI",
    "EE": "EST", "SZ": "SWZ", "ET": "ETH", "FJ": "FJI", "FI": "FIN",
    "FR": "FRA", "GA": "GAB", "GM": "GMB", "GE": "GEO", "DE": "DEU",
    "GH": "GHA", "GR": "GRC", "GD": "GRD", "GT": "GTM", "GN": "GIN",
    "GW": "GNB", "GY": "GUY", "HT": "HTI", "HN": "HND", "HU": "HUN",
    "IS": "ISL", "IN": "IND", "ID": "IDN", "IR": "IRN", "IQ": "IRQ",
    "IE": "IRL", "IL": "ISR", "IT": "ITA", "JM": "JAM", "JP": "JPN",
    "JO": "JOR", "KZ": "KAZ", "KE": "KEN", "KI": "KIR", "KP": "PRK",
    "KR": "KOR", "KW": "KWT", "KG": "KGZ", "LA": "LAO", "LV": "LVA",
    "LB": "LBN", "LS": "LSO", "LR": "LBR", "LY": "LBY", "LI": "LIE",
    "LT": "LTU", "LU": "LUX", "MG": "MDG", "MW": "MWI", "MY": "MYS",
    "MV": "MDV", "ML": "MLI", "MT": "MLT", "MH": "MHL", "MR": "MRT",
    "MU": "MUS", "MX": "MEX", "FM": "FSM", "MD": "MDA", "MC": "MCO",
    "MN": "MNG", "ME": "MNE", "MA": "MAR", "MZ": "MOZ", "MM": "MMR",
    "NA": "NAM", "NR": "NRU", "NP": "NPL", "NL": "NLD", "NZ": "NZL",
    "NI": "NIC", "NE": "NER", "NG": "NGA", "MK": "MKD", "NO": "NOR",
    "OM": "OMN", "PK": "PAK", "PW": "PLW", "PA": "PAN", "PG": "PNG",
    "PY": "PRY", "PE": "PER", "PH": "PHL", "PL": "POL", "PT": "PRT",
    "QA": "QAT", "RO": "ROU", "RU": "RUS", "RW": "RWA", "KN": "KNA",
    "LC": "LCA", "VC": "VCT", "WS": "WSM", "SM": "SMR", "ST": "STP",
    "SA": "SAU", "SN": "SEN", "RS": "SRB", "SC": "SYC", "SL": "SLE",
    "SG": "SGP", "SK": "SVK", "SI": "SVN", "SB": "SLB", "SO": "SOM",
    "ZA": "ZAF", "SS": "SSD", "ES": "ESP", "LK": "LKA", "SD": "SDN",
    "SR": "SUR", "SE": "SWE", "CH": "CHE", "SY": "SYR", "TJ": "TJK",
    "TZ": "TZA", "TH": "THA", "TL": "TLS", "TG": "TGO", "TO": "TON",
    "TT": "TTO", "TN": "TUN", "TR": "TUR", "TM": "TKM", "TV": "TUV",
    "UG": "UGA", "UA": "UKR", "AE": "ARE", "GB": "GBR", "US": "USA",
    "UY": "URY", "UZ": "UZB", "VU": "VUT", "VE": "VEN", "VN": "VNM",
    "YE": "YEM", "ZM": "ZMB", "ZW": "ZWE",
}


def standardize_country_code(code: str) -> str:
    """Standardize a country code to ISO 3166-1 alpha-3 format.

    Parameters
    ----------
    code : str
        Country code (ISO2 or ISO3).

    Returns
    -------
    str
        ISO3 country code (upper-cased).
    """
    if len(code) == 2:
        return ISO2_TO_ISO3.get(code.upper(), code.upper())
    return code.upper()
