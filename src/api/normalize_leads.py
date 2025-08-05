"""
normalize_leads.py
Utility to map raw, customer-specific form submissions
into the canonical schema expected by the Noteefy-AI-Lead-Scorer prompt.
"""

import json
from pathlib import Path
from typing import Dict, List

# ── Load static seeds ──────────────────────────────────────────
# Adjust the path if you saved the JSON files elsewhere.
BASE_DIR = Path(__file__).parent / "data"
PRICING  = json.loads((BASE_DIR / "pricing_seed.json").read_text())
PRESETS  = json.loads((BASE_DIR / "fixed_presets.json").read_text())

# ── Normalizer -------------------------------------------------
def normalize_batch(payload: Dict) -> Dict:
    """
    Convert raw submissions into canonical lead objects.

    Expected input:  { "leads": [ { "_id":{...}, "submission_data": {...} }, ... ] }
    Output format:   { "leads": [ { _id, group_size, preferred_lodging_type,
                                    desired_date_ranges, text_opt_in,
                                    email_opt_in, notes }, ... ] }
    """
    raw_leads = payload.get("leads", [])
    cleaned: List[Dict] = []

    for lead in raw_leads:
        sd = lead.get("submission_data", {})

        # --- helpers -----------------------------------------------------
        def first(keys: List[str]):
            """Return first matching value for any of the partial-key strings."""
            for k, v in sd.items():
                if any(term in k.lower() for term in keys):
                    return v
            return None

        # --- extract fields ---------------------------------------------
        group_size = int(first(["group size", "size"]) or 1)

        lodging = []
        for k, v in sd.items():
            if "lodging option" in k.lower() or "lodging" in k.lower():
                lodging += v if isinstance(v, list) else [v]

        date_ranges = sd.get("SelectedDateRanges", [])
        notes       = first(["comment", "instruction", "note"]) or ""

        cleaned.append(
            {
                "_id": lead["_id"]["$oid"],
                "group_size": group_size,
                "preferred_lodging_type": lodging or ["Any"],
                "desired_date_ranges": date_ranges,
                "text_opt_in": any("text update" in k.lower() and sd[k] for k in sd),
                "email_opt_in": any("email update" in k.lower() and sd[k] for k in sd),
                "notes": notes,
            }
        )
        nights = max((pd.parse(end) - pd.parse(start)).days
             for rng in date_ranges
             for start, end in [map(str.strip, rng.split('-'))])  # pandas opcional
        price_per_night = min(PRICING.get(lod, 0) for lod in lodging or PRICING)
        est_rev = nights * price_per_night * group_size
        lead_obj["estimated_revenue"] = est_rev


    return {"leads": cleaned}
