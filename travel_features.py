import html
import io
import json
import os
import re
import threading
import time
from datetime import date, timedelta
from functools import lru_cache
from typing import Any

import psycopg
import requests
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


DESTINATION_COORDINATES = {
    "bali": (-8.4095, 115.1889),
    "bangkok": (13.7563, 100.5018),
    "dubai": (25.2048, 55.2708),
    "istanbul": (41.0082, 28.9784),
    "london": (51.5072, -0.1276),
    "new york": (40.7128, -74.0060),
    "paris": (48.8566, 2.3522),
    "rome": (41.9028, 12.4964),
    "singapore": (1.3521, 103.8198),
    "tokyo": (35.6762, 139.6503),
}

WEATHER_DESCRIPTIONS = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Rime fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Heavy drizzle",
    61: "Light rain",
    63: "Rain",
    65: "Heavy rain",
    71: "Light snow",
    73: "Snow",
    75: "Heavy snow",
    80: "Rain showers",
    81: "Rain showers",
    82: "Heavy rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Thunderstorm with hail",
}
_nominatim_lock = threading.Lock()
_last_nominatim_request = 0.0


def _database_url() -> str:
    from dotenv import load_dotenv

    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not configured.")
    return url


def initialize_trip_history() -> None:
    with psycopg.connect(_database_url(), connect_timeout=5) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS travel_plans (
                id BIGSERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                destination TEXT NOT NULL,
                start_date DATE NOT NULL,
                travelers INTEGER NOT NULL CHECK (travelers > 0),
                duration_days INTEGER NOT NULL CHECK (duration_days > 0),
                budget NUMERIC(14, 2) NOT NULL CHECK (budget >= 0),
                currency TEXT NOT NULL,
                travel_style TEXT NOT NULL,
                trip_request TEXT NOT NULL,
                flight_results TEXT NOT NULL DEFAULT '',
                hotel_results TEXT NOT NULL DEFAULT '',
                itinerary TEXT NOT NULL DEFAULT '',
                final_response TEXT NOT NULL DEFAULT '',
                weather_json JSONB NOT NULL DEFAULT '[]'::jsonb,
                map_points_json JSONB NOT NULL DEFAULT '[]'::jsonb,
                latitude DOUBLE PRECISION,
                longitude DOUBLE PRECISION,
                departure_iata TEXT NOT NULL DEFAULT 'DAC',
                arrival_iata TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        connection.execute(
            "ALTER TABLE travel_plans ADD COLUMN IF NOT EXISTS "
            "map_points_json JSONB NOT NULL DEFAULT '[]'::jsonb"
        )
        connection.execute(
            "ALTER TABLE travel_plans ADD COLUMN IF NOT EXISTS "
            "departure_iata TEXT NOT NULL DEFAULT 'DAC'"
        )
        connection.execute(
            "ALTER TABLE travel_plans ADD COLUMN IF NOT EXISTS "
            "arrival_iata TEXT NOT NULL DEFAULT ''"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS travel_plans_user_updated_idx "
            "ON travel_plans (user_id, updated_at DESC)"
        )


def list_user_trips(user_id: str) -> list[dict[str, Any]]:
    with psycopg.connect(_database_url(), connect_timeout=5) as connection:
        rows = connection.execute(
            """
            SELECT id, destination, start_date, duration_days, travel_style,
                   trip_request, updated_at
            FROM travel_plans
            WHERE user_id = %s
            ORDER BY updated_at DESC
            LIMIT 30
            """,
            (user_id,),
        ).fetchall()
    return [
        {
            "id": row[0],
            "destination": row[1],
            "start_date": row[2],
            "duration_days": row[3],
            "travel_style": row[4],
            "trip_request": row[5],
            "updated_at": row[6],
        }
        for row in rows
    ]


def get_trip(user_id: str, trip_id: int) -> dict[str, Any] | None:
    with psycopg.connect(_database_url(), connect_timeout=5) as connection:
        row = connection.execute(
            """
            SELECT id, user_id, destination, start_date, travelers, duration_days,
                   budget, currency, travel_style, trip_request, flight_results,
                   hotel_results, itinerary, final_response, weather_json,
                   map_points_json, latitude, longitude, created_at, updated_at,
                   departure_iata, arrival_iata
            FROM travel_plans
            WHERE user_id = %s AND id = %s
            """,
            (user_id, trip_id),
        ).fetchone()
    if row is None:
        return None
    return {
        "id": row[0],
        "user_id": row[1],
        "destination": row[2],
        "start_date": row[3],
        "travelers": row[4],
        "duration_days": row[5],
        "budget": float(row[6]),
        "currency": row[7],
        "travel_style": row[8],
        "trip_request": row[9],
        "flight_results": row[10],
        "hotel_results": row[11],
        "itinerary": row[12],
        "final_response": row[13],
        "weather": row[14],
        "map_points": row[15],
        "latitude": row[16],
        "longitude": row[17],
        "created_at": row[18],
        "updated_at": row[19],
        "departure_iata": row[20],
        "arrival_iata": row[21],
    }


def save_trip(
    trip: dict[str, Any],
    trip_id: int | None = None,
) -> int:
    values = (
        trip["user_id"],
        trip["destination"],
        trip["start_date"],
        trip["travelers"],
        trip["duration_days"],
        trip["budget"],
        trip["currency"],
        trip["travel_style"],
        trip["trip_request"],
        trip["flight_results"],
        trip["hotel_results"],
        trip["itinerary"],
        trip["final_response"],
        json.dumps(trip.get("weather", [])),
        json.dumps(trip.get("map_points", [])),
        trip.get("latitude"),
        trip.get("longitude"),
        trip.get("departure_iata", "DAC"),
        trip.get("arrival_iata", ""),
    )
    with psycopg.connect(_database_url(), connect_timeout=5) as connection:
        if trip_id is None:
            row = connection.execute(
                """
                INSERT INTO travel_plans (
                    user_id, destination, start_date, travelers, duration_days,
                    budget, currency, travel_style, trip_request, flight_results,
                    hotel_results, itinerary, final_response, weather_json,
                    map_points_json, latitude, longitude, departure_iata,
                    arrival_iata
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s::jsonb, %s::jsonb, %s, %s, %s, %s)
                RETURNING id
                """,
                values,
            ).fetchone()
            return int(row[0])

        row = connection.execute(
            """
            UPDATE travel_plans
            SET destination = %s, start_date = %s, travelers = %s,
                duration_days = %s, budget = %s, currency = %s,
                travel_style = %s, trip_request = %s, flight_results = %s,
                hotel_results = %s, itinerary = %s, final_response = %s,
                weather_json = %s::jsonb, map_points_json = %s::jsonb,
                latitude = %s, longitude = %s, departure_iata = %s,
                arrival_iata = %s,
                updated_at = NOW()
            WHERE id = %s AND user_id = %s
            RETURNING id
            """,
            (
                *values[1:],
                trip_id,
                values[0],
            ),
        ).fetchone()
        if row is None:
            raise LookupError("The selected saved trip no longer exists.")
        return int(row[0])


def resolve_destination(destination: str) -> dict[str, Any]:
    normalized = destination.strip().casefold()
    if normalized in DESTINATION_COORDINATES:
        latitude, longitude = DESTINATION_COORDINATES[normalized]
        return {
            "name": destination.strip().title(),
            "latitude": latitude,
            "longitude": longitude,
        }

    response = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": destination, "count": 1, "language": "en", "format": "json"},
        timeout=10,
    )
    response.raise_for_status()
    results = response.json().get("results", [])
    if not results:
        raise LookupError(f"Could not find map coordinates for {destination!r}.")
    result = results[0]
    return {
        "name": result.get("name", destination),
        "latitude": float(result["latitude"]),
        "longitude": float(result["longitude"]),
        "country": result.get("country", ""),
    }


@lru_cache(maxsize=256)
def _resolve_landmark(destination: str) -> dict[str, Any] | None:
    global _last_nominatim_request
    with _nominatim_lock:
        elapsed = time.monotonic() - _last_nominatim_request
        if elapsed < 1:
            time.sleep(1 - elapsed)
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": destination, "format": "jsonv2", "limit": 1},
            headers={"User-Agent": "WayfarerAITravelPlanner/1.0 (personal travel planner)"},
            timeout=10,
        )
        _last_nominatim_request = time.monotonic()
    response.raise_for_status()
    results = response.json()
    if not results:
        return None
    result = results[0]
    return {
        "name": result.get("name") or destination,
        "latitude": float(result["lat"]),
        "longitude": float(result["lon"]),
    }


def resolve_itinerary_locations(
    destination: str,
    itinerary: str,
    limit: int = 6,
) -> tuple[list[dict[str, Any]], list[str]]:
    base_location = resolve_destination(destination)
    points = [base_location]
    normalized_names = {destination.casefold()}
    section_match = re.search(
        r"(?ims)^#{1,4}\s*(?:map locations|key places to map)\s*\n(.*?)(?=^#{1,4}\s|\Z)",
        itinerary,
    )
    if not section_match:
        return points, []

    location_names = []
    for line in section_match.group(1).splitlines():
        name = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s*", "", line).strip()
        name = re.split(r"\s+(?:—|–|-)\s+Day\s+\d+\b", name, maxsplit=1, flags=re.I)[0]
        name = re.sub(r"\s*\([^)]*\)\s*$", "", name).strip(" .")
        key = name.casefold()
        if name and key not in normalized_names:
            normalized_names.add(key)
            location_names.append(name)

    unresolved = []
    for name in location_names[:limit]:
        try:
            point = resolve_destination(f"{name}, {destination}")
        except LookupError:
            point = _resolve_landmark(f"{name}, {destination}")
            if point is None:
                unresolved.append(name)
                continue
        point["name"] = name
        points.append(point)
    unresolved.extend(location_names[limit:])
    return points, unresolved


def fetch_weather_forecast(
    latitude: float,
    longitude: float,
    start_date: date,
    duration_days: int,
) -> dict[str, Any]:
    today = date.today()
    latest_forecast_date = today + timedelta(days=15)
    if start_date < today:
        return {
            "available": False,
            "message": "Weather forecasts are not available for past travel dates.",
            "days": [],
        }
    if start_date > latest_forecast_date:
        return {
            "available": False,
            "message": (
                "Forecasts are currently available only for the next 16 days. "
                "Check the weather again closer to departure."
            ),
            "days": [],
        }

    end_date = min(
        start_date + timedelta(days=duration_days - 1),
        latest_forecast_date,
    )
    response = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": latitude,
            "longitude": longitude,
            "daily": (
                "weather_code,temperature_2m_max,temperature_2m_min,"
                "precipitation_probability_max"
            ),
            "timezone": "auto",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
        timeout=10,
    )
    response.raise_for_status()
    daily = response.json().get("daily", {})
    days = []
    for index, forecast_date in enumerate(daily.get("time", [])):
        code = daily.get("weather_code", [None])[index]
        days.append(
            {
                "date": forecast_date,
                "condition": WEATHER_DESCRIPTIONS.get(code, "Weather data"),
                "high_c": daily.get("temperature_2m_max", [None])[index],
                "low_c": daily.get("temperature_2m_min", [None])[index],
                "rain_chance": daily.get("precipitation_probability_max", [None])[index],
            }
        )
    return {
        "available": bool(days),
        "message": (
            f"Forecast available through {end_date.isoformat()}."
            if end_date < start_date + timedelta(days=duration_days - 1)
            else ""
        ),
        "days": days,
    }


def calculate_budget_breakdown(
    budget: float,
) -> list[dict[str, Any]]:
    categories = (
        ("Flights", 0.35),
        ("Accommodation", 0.35),
        ("Food", 0.15),
        ("Local transport", 0.08),
        ("Activities", 0.07),
    )
    rows = []
    allocated = 0.0
    for index, (category, share) in enumerate(categories):
        estimate = (
            round(budget - allocated, 2)
            if index == len(categories) - 1
            else round(budget * share, 2)
        )
        allocated += estimate
        rows.append(
            {
                "category": category,
                "share": f"{share:.0%}",
                "estimate": estimate,
            }
        )
    return rows


def create_trip_pdf(
    title: str,
    trip_details: str,
    itinerary: str,
    budget_rows: list[dict[str, Any]],
    currency: str,
    weather: list[dict[str, Any]],
    final_response: str,
) -> bytes:
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=20 * mm,
        bottomMargin=18 * mm,
        title=title,
        author="Wayfarer AI",
    )
    base = getSampleStyleSheet()
    heading = ParagraphStyle(
        "TripHeading",
        parent=base["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=25,
        textColor=colors.HexColor("#10513f"),
        spaceAfter=8,
    )
    section = ParagraphStyle(
        "TripSection",
        parent=base["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=17,
        textColor=colors.HexColor("#176b52"),
        spaceBefore=12,
        spaceAfter=6,
    )
    body = ParagraphStyle(
        "TripBody",
        parent=base["BodyText"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#26372f"),
        spaceAfter=4,
    )
    font_path = r"C:\Windows\Fonts\Nirmala.ttf"
    if os.path.isfile(font_path):
        if "NirmalaUI" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("NirmalaUI", font_path))
        heading.fontName = "NirmalaUI"
        section.fontName = "NirmalaUI"
        body.fontName = "NirmalaUI"

    story: list[Any] = [
        Paragraph(html.escape(title), heading),
        Paragraph("Prepared by Wayfarer AI", body),
        Spacer(1, 6),
        Paragraph("Trip details", section),
    ]
    for line in trip_details.splitlines():
        if line.strip():
            story.append(Paragraph(html.escape(line), body))

    if budget_rows:
        story.append(Paragraph("Estimated budget breakdown", section))
        table_data = [["Category", "Share", f"Estimate ({currency})"]]
        table_data.extend(
            [
                [
                    row["category"],
                    row["share"],
                    f"{row['estimate']:,.2f}",
                ]
                for row in budget_rows
            ]
        )
        table = Table(table_data, colWidths=[75 * mm, 35 * mm, 60 * mm], repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#176b52")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#dce5dd")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f7f3")]),
                    ("PADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story.extend([table, Spacer(1, 4)])

    if weather:
        story.append(Paragraph("Weather forecast", section))
        for day in weather:
            story.append(
                Paragraph(
                    html.escape(
                        f"{day['date']}: {day['condition']}, "
                        f"{day['low_c']}–{day['high_c']} °C, "
                        f"rain chance {day['rain_chance']}%"
                    ),
                    body,
                )
            )

    for section_title, content in (
        ("Day-by-day itinerary", itinerary),
        ("Final travel plan", final_response),
    ):
        if content:
            story.append(Paragraph(section_title, section))
            for line in content.splitlines():
                cleaned = re.sub(r"[*_`#]", "", line).strip()
                if cleaned:
                    story.append(Paragraph(html.escape(cleaned), body))

    document.build(story)
    return buffer.getvalue()
