import os
from datetime import date

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("AVIATIONSTACK_API_KEY")
FLIGHTS_URL = "https://api.aviationstack.com/v1/flights"


def search_flights(
    departure_iata: str,
    arrival_iata: str,
    flight_date: date,
) -> str:
    departure_code = departure_iata.strip().upper()
    arrival_code = arrival_iata.strip().upper()
    if not departure_code or not arrival_code:
        raise ValueError("Enter both departure and arrival airport IATA codes.")
    if not departure_code.isalpha() or len(departure_code) != 3:
        raise ValueError("Departure airport code must be three letters (for example, DAC).")
    if not arrival_code.isalpha() or len(arrival_code) != 3:
        raise ValueError("Arrival airport code must be three letters (for example, CDG).")
    if not API_KEY:
        raise RuntimeError("AVIATIONSTACK_API_KEY is not configured.")

    try:
        response = requests.get(
            FLIGHTS_URL,
            params={
                "access_key": API_KEY,
                "dep_iata": departure_code,
                "arr_iata": arrival_code,
                "limit": 5,
            },
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        status = error.response.status_code if error.response is not None else None
        if status is not None:
            raise RuntimeError(
                f"AviationStack flight request failed (HTTP {status})."
            ) from error
        raise RuntimeError("Could not connect to AviationStack.") from error

    try:
        payload = response.json()
    except ValueError as error:
        raise RuntimeError("AviationStack returned an invalid response.") from error

    if not isinstance(payload, dict):
        raise RuntimeError("AviationStack returned an unexpected response format.")

    api_error = payload.get("error")
    if api_error:
        if isinstance(api_error, dict):
            message = api_error.get("message", "Unknown API error")
            code = api_error.get("code")
            detail = f"{message} ({code})" if code else message
        else:
            detail = str(api_error)
        raise RuntimeError(f"AviationStack error: {detail}")

    flights = payload.get("data")
    if not isinstance(flights, list):
        raise RuntimeError("AviationStack response did not contain a flight list.")
    matching_flights = []
    for flight in flights:
        if not isinstance(flight, dict):
            continue
        departure = flight.get("departure") or {}
        arrival = flight.get("arrival") or {}
        if (
            str(departure.get("iata", "")).upper() == departure_code
            and str(arrival.get("iata", "")).upper() == arrival_code
        ):
            matching_flights.append(flight)

    if not matching_flights:
        return (
            f"No live flight records were found for {departure_code} to {arrival_code}. "
            "This endpoint does not provide schedules for future trip dates."
        )

    results = [
        f"Live flights matching {departure_code} to {arrival_code}; "
        f"these are not schedules for {flight_date.isoformat()}:"
    ]
    for schedule in matching_flights[:5]:
        airline = schedule.get("airline") or {}
        flight = schedule.get("flight") or {}
        departure = schedule.get("departure") or {}
        arrival = schedule.get("arrival") or {}
        results.append(
            "\n".join(
                (
                    f"Airline and flight: {airline.get('name', 'Unknown airline')} "
                    f"{flight.get('iata') or flight.get('number', 'Unknown')}",
                    f"Route: {departure.get('iata', departure_code)} to "
                    f"{arrival.get('iata', arrival_code)}",
                    f"Scheduled departure: {departure.get('scheduled', 'Time unavailable')}",
                    f"Scheduled arrival: {arrival.get('scheduled', 'Time unavailable')}",
                    f"Status: {schedule.get('flight_status', 'Scheduled')}",
                )
            )
        )
    return "\n\n".join(results)
