"""Shape of the synthetic Aurelia world. Everything here is invented for the demo."""

# Market code -> relative size (Market C is the reference size of 1.0).
MARKETS: dict[str, float] = {
    "A": 1.6, "B": 1.3, "C": 1.0, "D": 0.9, "E": 0.8, "F": 0.7, "G": 0.6, "H": 0.5,
}

# Four distribution centres serve two markets each.
DC_OF: dict[str, str] = {
    "A": "DC1", "B": "DC1", "C": "DC2", "D": "DC2",
    "E": "DC3", "F": "DC3", "G": "DC4", "H": "DC4",
}

# base: daily units per SKU per market at size 1.0 (min, max)
# price: unit price range in EUR, margin: mean gross margin fraction
# amp / peak_day: yearly seasonality (fraction of base, day of year of the peak)
# sea_days / air_days: replenishment lead times
CATEGORIES: dict[str, dict] = {
    "jewelry":     dict(base=(8, 20),   price=(60, 300), margin=0.55, amp=0.25, peak_day=340, sea_days=35, air_days=6),
    "electronics": dict(base=(25, 50),  price=(80, 900), margin=0.22, amp=0.25, peak_day=325, sea_days=42, air_days=7),
    "clothing":    dict(base=(50, 90),  price=(20, 120), margin=0.50, amp=0.15, peak_day=300, sea_days=38, air_days=6),
    "beauty":      dict(base=(70, 120), price=(8, 60),   margin=0.60, amp=0.15, peak_day=345, sea_days=28, air_days=5),
    "home":        dict(base=(60, 110), price=(15, 150), margin=0.40, amp=0.15, peak_day=110, sea_days=40, air_days=7),
}

SKUS_PER_CATEGORY = 12
N_DAYS = 730

# Monday..Sunday demand shape.
WEEKDAY_SHAPE = [0.90, 0.90, 0.95, 1.00, 1.10, 1.25, 1.15]

EVENT_KINDS = ["competitor_price_cut", "social_trend", "weather", "local_event"]

# Scripted scenario that matches the demo: a competitor price cut lifts Home in Market C.
DEMO_MARKET = "C"
DEMO_CATEGORY = "home"
DEMO_MULTIPLIER = 1.5
DEMO_RAMP_DAYS = 4
DEMO_DAYS_AGO = 5          # event starts this many days before the last data day
DEMO_STOCK_COVER = 0.60    # uncommitted stock covers this share of the 14-day lift

AIR_COST_MULTIPLIER = 1.18

# Customer segments: share of baseline demand, and share of the uplift by event kind.
# For a competitor price cut, value_seeker_repeat + promo_hunter carry 68% of the uplift.
SEGMENTS = ["loyal_full_price", "value_seeker_repeat", "promo_hunter", "occasional"]
SEGMENT_BASE_SHARE = [0.40, 0.25, 0.10, 0.25]
SEGMENT_UPLIFT_SHARE = {
    "competitor_price_cut": [0.12, 0.50, 0.18, 0.20],
    "social_trend":         [0.15, 0.10, 0.10, 0.65],
    "weather":              [0.30, 0.15, 0.05, 0.50],
    "local_event":          [0.20, 0.10, 0.10, 0.60],
}

# Orchestrator policy. Assumptions are named so the backtest can report against them.
DEFAULT_BUDGET_EUR = 40_000
BUDGET_CAP_EUR = 60_000          # requests above this are blocked
APPROVAL_LIMIT_EUR = 15_000      # budget changes above this need a human
MARGIN_FLOOR_PCT = 15.0          # category margin after promo depth must stay above this
REALLOC_SHARE = 0.60             # share of freed budget moved to a surplus category
SURPLUS_ROI = 1.8                # assumed return on reallocated spend (measured in the backtest)
HORIZON_DAYS = 14
CHANNELS = ["paid_search", "paid_social", "email", "app_push", "onsite"]
OFFER_TYPES = ["bundle", "threshold_discount", "loyalty_points", "free_shipping"]
BANNED_CLAIMS = ["guaranteed", "cheapest", "best price", "lowest price", "risk-free", "#1"]
