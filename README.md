# Wayfarer AI Travel Planner

Wayfarer is a Streamlit travel-planning app. It combines a LangGraph agent
workflow with flight and hotel research, then creates a day-by-day trip plan.

## Features

- Trip form for destination, departure date, travelers, duration, budget,
  currency, and travel style.
- Destination and sample-trip buttons that fill in the form.
- Flight and hotel research using AviationStack and Tavily.
- Route-filtered live flight research using departure and arrival IATA airport
  codes.
- AI-generated daily itinerary and final trip summary using Groq.
- Estimated flight, accommodation, food, local transport, and activity budget
  breakdown.
- PostgreSQL-backed trip history, with options to load and update saved trips.
- Destination and itinerary-place map, plus an Open-Meteo forecast when the
  departure date is within the available forecast window.
- PDF and Markdown downloads.

Prices in the budget breakdown are planning estimates, not live quotes or
confirmed bookings. Weather forecasts are available only for dates within the
next 16 days.

## Requirements

- Python
- PostgreSQL
- API keys for Groq and Tavily
- An AviationStack API key for flight search
- AviationStack Basic or higher only if future flight schedules are needed

## Windows setup

Open PowerShell in the project folder:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell prevents environment activation, run the environment's Python
directly instead:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Create a PostgreSQL database, for example `AI_travelPlaner`. On first app
startup, the application creates the `travel_plans` table and its index.
The LangGraph checkpointer also creates its own tables.

## Environment variables

Create a `.env` file in the project folder. Replace the example values with
your own credentials and API keys:

```dotenv
DATABASE_URL=postgresql://postgres:YOUR_DATABASE_PASSWORD@localhost:5432/AI_travelPlaner
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-120b
TAVILY_API_KEY=your_tavily_api_key
AVIATIONSTACK_API_KEY=your_aviationstack_api_key
```

Keep `.env` private. It is listed in `.gitignore`; never commit passwords or
API keys to GitHub. If a key has been exposed, rotate it with its provider.
`GROQ_MODEL` is optional; when omitted, the app uses `openai/gpt-oss-120b`.
Flight search defaults to Dhaka's `DAC` airport code; enter the destination's
three-letter IATA code in the trip form (for example, `CDG` for Paris).
AviationStack's live flight results are filtered to that route, but they are
not schedules for a future trip date. Future schedules require AviationStack's
Basic or higher plan and a supported schedule endpoint. If no matching live
route records are available, the app says so rather than showing unrelated
flights.

## Run the app

```powershell
streamlit run frontend.py
```

Then open the local URL shown in the terminal, usually `http://localhost:8501`.

## External services

- **Groq** runs the travel-planning language model.
- **Tavily** searches for hotel information.
- **AviationStack** provides flight research.
- **Open-Meteo** provides geocoding and weather forecasts.
- **OpenStreetMap Nominatim** resolves itinerary landmarks for the map.

Live provider results depend on network access, service availability, and valid
API credentials. The app does not book flights or hotels.
