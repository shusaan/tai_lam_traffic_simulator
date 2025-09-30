from datetime import datetime

# -------------------------
# Date Ranges
# -------------------------
START_DATE = datetime(2025, 2, 1)
END_DATE = datetime(2025, 9, 23)
POLICY_CHANGE_DATE = datetime(2025, 5, 31)

# -------------------------
# Data Sources
# -------------------------
LIST_API = "https://api.data.gov.hk/v1/historical-archive/list-file-versions"
GET_API = "https://api.data.gov.hk/v1/historical-archive/get-file"
RAW_URL = "https://resource.data.one.gov.hk/td/traffic-detectors/rawSpeedVol-all.xml"
LOCATIONS_CSV_URL = "https://static.data.gov.hk/td/traffic-data-strategic-major-roads/info/traffic_speed_volume_occ_info.csv"

# -------------------------
# Local Paths
# -------------------------
DATA_DIR = "xml_cache"  # local cache folder
CACHE_FILE = "hk_tunnel_traffic.csv"

# -------------------------
# Toll Assumptions (HKD)
# -------------------------
TOLL_BEFORE = 65
TOLL_PEAK = 45
TOLL_OFFPEAK = 30

# -------------------------
# Corridor Mapping
# -------------------------
CORRIDOR_KEYWORDS = {
    "tai_lam": ["Tai Lam"],
    "nt_circular": ["Tuen Mun Road", "NT Circular"]
}

# -------------------------
# Parallel downloads
# -------------------------
MAX_WORKERS = 25
