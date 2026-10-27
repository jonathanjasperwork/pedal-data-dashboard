
import json
from pathlib import Path
import zipfile
import pandas as pd


# DATA_PATH = Path("data/padel_courts.json")
DATA_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "padel_courts.json.zip"
)

VALID_TIERS = {"premium", "standard", "budget"}
VALID_STATUSES = {
    "opened",
    "closed",
    "missing-data",
    "coming-soon",
}


def load_padel_data(path=DATA_PATH):

    with zipfile.ZipFile(path, "r") as archive:
        json_files = [
            name for name in archive.namelist()
            if name.lower().endswith(".json")
            and not name.startswith("__MACOSX/")
        ]

        if len(json_files) != 1:
            raise ValueError(
                f"Expected exactly one JSON file in ZIP; "
                f"found {len(json_files)}."
            )

        with archive.open(json_files[0], "r") as file:
            raw = json.load(file)

    # with open(path, "r", encoding="utf-8") as file:
    #     raw = json.load(file)

    if not isinstance(raw, list):
        raise ValueError("Expected a JSON array of courts.")

    court_rows = []
    slot_rows = []

    for court in raw:
        court_id = str(court.get("id", ""))

        tier = court.get("tier")
        status = court.get("published")

        court_rows.append({
            "court_id": court_id,
            "name": court.get("name"),
            "subname": court.get("subname"),
            "tier": tier if tier in VALID_TIERS else None,
            "rating": pd.to_numeric(
                court.get("rating"), errors="coerce"
            ),
            "link": court.get("link"),
            "loc_type": court.get("loc_type"),
            "city": court.get("loc_name"),
            "province": court.get("province"),
            "published": (
                status if status in VALID_STATUSES else None
            ),
        })

        for field in court.get("field_list") or []:
            descriptions = {
                item.get("title"): item.get("content")
                for item in field.get("desc_point") or []
            }

            schedules = field.get("schedule") or {}

            for day_name, slots in schedules.items():
                if not isinstance(slots, list):
                    continue

                for slot in slots:
                    start = slot.get("start_time")
                    end = slot.get("end_time")

                    slot_rows.append({
                        "court_id": court_id,
                        "name": court.get("name"),
                        "tier": tier,
                        "published": status,
                        "city": court.get("loc_name"),
                        "province": court.get("province"),
                        "rating": pd.to_numeric(
                            court.get("rating"),
                            errors="coerce",
                        ),
                        "field_id": field.get("id"),
                        "sport_type_id": field.get(
                            "sport_type_id"
                        ),
                        "court_type": descriptions.get(
                            "Jenis lapangan"
                        ),
                        "surface": descriptions.get(
                            "Jenis Alas"
                        ),
                        "day_name": day_name,
                        "date": slot.get("date"),
                        "start_time": start,
                        "end_time": end,
                        "price": pd.to_numeric(
                            slot.get("price"),
                            errors="coerce",
                        ),
                        "strike_price": pd.to_numeric(
                            slot.get("strike_price"),
                            errors="coerce",
                        ),
                        "duration_minutes": pd.to_numeric(
                            slot.get("duration_per_session"),
                            errors="coerce",
                        ),
                    })

    courts_df = pd.DataFrame(court_rows)
    slots_df = pd.DataFrame(slot_rows)

    if not courts_df.empty:
        courts_df["rating"] = pd.to_numeric(
            courts_df["rating"], errors="coerce"
        )

    if not slots_df.empty:
        slots_df["date"] = pd.to_datetime(
            slots_df["date"], errors="coerce"
        )
        slots_df["start_hour"] = pd.to_datetime(
            slots_df["start_time"],
            format="%H:%M:%S",
            errors="coerce",
        ).dt.hour

        slots_df["price_per_hour"] = (
            slots_df["price"]
            / slots_df["duration_minutes"].replace(0, float("nan"))
            * 60
        )

        slots_df["discount_pct"] = (
            (
                slots_df["strike_price"] - slots_df["price"]
            )
            / slots_df["strike_price"].replace(
                0, float("nan")
            )
            * 100
        )

    return courts_df, slots_df
