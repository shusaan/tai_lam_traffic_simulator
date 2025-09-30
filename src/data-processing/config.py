"""Data Processing Configuration for Hong Kong Traffic Data"""

from datetime import datetime
import os

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
# Local Paths (consistent with project structure)
# -------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "xml_cache")
CACHE_FILE = os.path.join(PROJECT_ROOT, "data", "hk_tunnel_traffic.csv")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "data", "analysis")

# -------------------------
# Toll Configuration (consistent with main config)
# -------------------------
TOLL_BEFORE = 65  # HKD before policy change
TOLL_PEAK = 45    # HKD peak hours after policy
TOLL_OFFPEAK = 30 # HKD off-peak hours after policy

# Base toll for simulation (consistent with main project)
BASE_TOLL = 30.0
MIN_TOLL = 18.0
MAX_TOLL = 55.0

# -------------------------
# Road Mapping (consistent with main project)
# -------------------------
CORRIDOR_KEYWORDS = {
    "tai_lam_tunnel": ["Tai Lam", "Tai Lam Tunnel"],
    "tuen_mun_road": ["Tuen Mun Road"],
    "nt_circular_road": ["NT Circular", "New Territories Circular Road"]
}

# -------------------------
# Processing Configuration
# -------------------------
MAX_WORKERS = 25
CHUNK_SIZE = 1000
TIMEOUT_SECONDS = 30
