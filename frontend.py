import re
from datetime import date, datetime, timedelta

import pandas as pd
import psycopg
import requests
import streamlit as st
from langchain_core.messages import HumanMessage

from main import app
from travel_features import (
    calculate_budget_breakdown,
    create_trip_pdf,
    fetch_weather_forecast,
    get_trip,
    initialize_trip_history,
    list_user_trips,
    resolve_itinerary_locations,
    save_trip,
)


st.set_page_config(
    page_title="AI Travel Planner",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="auto",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap');

    :root {
        color-scheme: light;
        --ink: #192b26;
        --muted: #64746d;
        --green: #176b52;
        --green-dark: #10513f;
        --line: #e4e9e4;
        --paper: #ffffff;
        --canvas: #f5f7f3;
    }

    html, body, .stApp {
        background: var(--canvas);
        color: var(--ink);
        font-family: 'DM Sans', sans-serif;
    }
    [data-testid="stAppViewContainer"] { background: var(--canvas); }
    [data-testid="stMainBlockContainer"] {
        max-width: 1240px;
        padding: 1.4rem 2.2rem 3rem;
    }
    #MainMenu, footer { visibility: hidden; }
    header[data-testid="stHeader"] { background: transparent; }

    section[data-testid="stSidebar"] {
        background: #fff;
        border-right: 1px solid var(--line);
    }
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] .stMarkdown { color: var(--ink); }
    section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
        padding-top: 1.5rem;
    }
    .sidebar-brand {
        color: var(--ink);
        font-family: 'Manrope', sans-serif;
        font-size: 1.12rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        padding: 0.3rem 0 0.8rem;
    }
    .sidebar-kicker {
        color: var(--muted);
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        margin: 1.35rem 0 0.55rem;
        text-transform: uppercase;
    }
    .sidebar-chip {
        background: #f6f8f5;
        border: 1px solid var(--line);
        border-radius: 10px;
        color: #43564e;
        font-size: 0.82rem;
        margin: 0.35rem 0;
        padding: 0.55rem 0.7rem;
    }

    .topbar {
        align-items: center;
        color: var(--muted);
        display: flex;
        font-size: 0.82rem;
        justify-content: space-between;
        margin: 0 0 1.1rem;
    }
    .topbar-brand {
        color: var(--ink);
        font-family: 'Manrope', sans-serif;
        font-size: 1.05rem;
        font-weight: 800;
        letter-spacing: -0.04em;
    }
    .topbar-note {
        background: #e8f2ed;
        border: 1px solid #d5e7dd;
        border-radius: 99px;
        color: var(--green-dark);
        font-size: 0.76rem;
        font-weight: 700;
        padding: 0.4rem 0.75rem;
    }

    .hero {
        align-items: flex-end;
        background-color: #203b32;
        background-image:
            linear-gradient(90deg, rgba(13, 35, 29, 0.88), rgba(13, 35, 29, 0.46) 58%, rgba(13, 35, 29, 0.08)),
            linear-gradient(0deg, rgba(13, 35, 29, 0.38), transparent 70%),
            url("https://images.unsplash.com/photo-1436491865332-7a61a109cc05?w=1800&q=85");
        background-position: center;
        background-size: cover;
        border-radius: 24px;
        box-shadow: 0 16px 38px rgba(27, 46, 37, 0.12);
        display: flex;
        min-height: 360px;
        overflow: hidden;
        padding: clamp(1.5rem, 5vw, 3.5rem);
        position: relative;
    }
    .hero-copy {
        max-width: 650px;
        position: relative;
        z-index: 1;
    }
    .hero-eyebrow {
        color: #cde6d7;
        font-size: 0.74rem;
        font-weight: 700;
        letter-spacing: 0.15em;
        margin-bottom: 0.9rem;
        text-transform: uppercase;
    }
    h1.hero-title {
        color: #fff !important;
        font-family: 'Manrope', sans-serif;
        font-size: clamp(2.15rem, 5vw, 4rem);
        font-weight: 800;
        letter-spacing: -0.055em;
        line-height: 1.08;
        margin: 0;
    }
    .hero-description {
        color: #e3eee8;
        font-size: clamp(0.94rem, 1.6vw, 1.08rem);
        line-height: 1.7;
        margin: 1rem 0 0;
        max-width: 540px;
    }
    .section-heading {
        color: var(--ink);
        font-family: 'Manrope', sans-serif;
        font-size: 1.2rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        margin: 1.9rem 0 0.25rem;
    }
    .section-caption {
        color: var(--muted);
        font-size: 0.9rem;
        margin: 0 0 0.9rem;
    }

    .destination-card {
        border: 1px solid rgba(22, 43, 35, 0.08);
        border-radius: 15px;
        height: 132px;
        overflow: hidden;
        position: relative;
    }
    .destination-card img {
        height: 100%;
        object-fit: cover;
        transition: transform 0.35s ease;
        width: 100%;
    }
    .destination-card:hover img { transform: scale(1.06); }
    .destination-shade {
        background: linear-gradient(0deg, rgba(10, 25, 20, 0.78), transparent 72%);
        inset: 0;
        position: absolute;
    }
    .destination-name {
        bottom: 11px;
        color: #fff;
        font-size: 0.9rem;
        font-weight: 700;
        left: 12px;
        position: absolute;
        text-shadow: 0 1px 5px rgba(0, 0, 0, 0.35);
    }

    [data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--paper);
        border: 1px solid var(--line);
        border-radius: 18px;
        box-shadow: 0 8px 26px rgba(36, 54, 43, 0.045);
    }
    .form-heading {
        color: var(--ink);
        font-family: 'Manrope', sans-serif;
        font-size: 1.35rem;
        font-weight: 800;
        letter-spacing: -0.035em;
        margin: 0 0 0.2rem;
    }
    .form-caption {
        color: var(--muted);
        font-size: 0.9rem;
        margin: 0 0 0.9rem;
    }
    .stTextArea textarea, .stTextInput input {
        background: #fbfcfa !important;
        border: 1px solid #dce4dc !important;
        border-radius: 12px !important;
        color: var(--ink) !important;
        font-size: 0.96rem !important;
    }
    .stTextArea textarea:focus, .stTextInput input:focus {
        border-color: #6da88a !important;
        box-shadow: 0 0 0 3px rgba(23, 107, 82, 0.1) !important;
    }
    .stTextArea textarea::placeholder, .stTextInput input::placeholder {
        color: #87958d !important;
    }
    .stTextArea label, .stTextInput label {
        color: #43564e !important;
        font-size: 0.84rem !important;
        font-weight: 700 !important;
    }
    div[data-testid="stButton"] > button {
        background: #fff !important;
        border: 1px solid #dfe7df !important;
        border-radius: 11px !important;
        color: #33483e !important;
        font-size: 0.82rem !important;
        font-weight: 600 !important;
        min-height: 2.55rem;
        transition: all 0.18s ease !important;
        white-space: normal !important;
        width: 100% !important;
    }
    div[data-testid="stButton"] > button:hover {
        background: #f1f7f2 !important;
        border-color: #8ab59a !important;
        color: var(--green-dark) !important;
    }
    div[data-testid="stButton"] > button:focus-visible {
        box-shadow: 0 0 0 3px rgba(23, 107, 82, 0.18) !important;
        outline: 2px solid var(--green) !important;
    }
    div[data-testid="stButton"] > button[kind="primary"] {
        background: var(--green) !important;
        border-color: var(--green) !important;
        border-radius: 12px !important;
        box-shadow: 0 7px 16px rgba(23, 107, 82, 0.18);
        color: #fff !important;
        font-size: 1rem !important;
        font-weight: 700 !important;
        min-height: 3.15rem;
    }
    div[data-testid="stButton"] > button[kind="primary"]:hover {
        background: var(--green-dark) !important;
        border-color: var(--green-dark) !important;
        color: #fff !important;
    }

    [data-testid="stStatusWidget"] {
        background: #fff !important;
        border: 1px solid var(--line) !important;
        border-radius: 14px !important;
        color: var(--ink) !important;
        margin: 0.5rem 0;
    }
    [data-testid="stStatusWidget"] * { color: var(--ink) !important; }
    [data-testid="stStatusWidget"] a { color: var(--green) !important; }
    .results-heading {
        border-bottom: 1px solid var(--line);
        color: var(--ink);
        font-family: 'Manrope', sans-serif;
        font-size: 1.35rem;
        font-weight: 800;
        letter-spacing: -0.035em;
        margin: 2rem 0 0.8rem;
        padding-bottom: 0.7rem;
    }
    .metric-row { display: flex; gap: 0.8rem; margin: 1rem 0; }
    .metric-box {
        background: #fff;
        border: 1px solid var(--line);
        border-radius: 14px;
        flex: 1;
        min-width: 0;
        padding: 1rem;
        text-align: center;
    }
    .metric-value {
        color: var(--green);
        font-family: 'Manrope', sans-serif;
        font-size: 1.55rem;
        font-weight: 800;
    }
    .metric-label {
        color: var(--muted);
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        margin-top: 0.15rem;
        text-transform: uppercase;
    }
    .save-note {
        background: #edf5ef;
        border: 1px solid #dceadf;
        border-radius: 11px;
        color: #385c49;
        font-size: 0.85rem;
        margin-top: 0.35rem;
        padding: 0.75rem 0.9rem;
    }
    div[data-testid="stDownloadButton"] > button {
        background: #fff !important;
        border: 1px solid #cbd9ce !important;
        border-radius: 11px !important;
        color: var(--green-dark) !important;
        font-weight: 700 !important;
        min-height: 2.8rem;
    }

    @media (max-width: 760px) {
        [data-testid="stMainBlockContainer"] { padding: 1rem 1rem 2rem; }
        .hero { border-radius: 18px; min-height: 330px; padding: 1.5rem; }
        .hero {
            background-image:
                linear-gradient(90deg, rgba(13, 35, 29, 0.82), rgba(13, 35, 29, 0.38)),
                linear-gradient(0deg, rgba(13, 35, 29, 0.38), transparent 70%),
                url("https://images.unsplash.com/photo-1436491865332-7a61a109cc05?w=1800&q=85");
        }
        div[data-testid="stHorizontalBlock"] {
            flex-wrap: wrap !important;
            gap: 0.65rem !important;
        }
        div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
            flex: 1 1 calc(50% - 0.65rem) !important;
            min-width: calc(50% - 0.65rem) !important;
        }
        .destination-card { height: 118px; }
        .metric-row { flex-wrap: wrap; }
        .metric-box { flex: 1 1 28%; padding: 0.75rem 0.45rem; }
        .metric-value { font-size: 1.3rem; }
    }
    @media (max-width: 420px) {
        [data-testid="stMainBlockContainer"] { padding-left: 0.75rem; padding-right: 0.75rem; }
        div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
            flex-basis: calc(50% - 0.65rem) !important;
            min-width: calc(50% - 0.65rem) !important;
        }
        .topbar-note { font-size: 0.68rem; }
        .hero { min-height: 300px; }
        .metric-box { flex-basis: 28%; }
    }
    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after { scroll-behavior: auto !important; transition-duration: 0.01ms !important; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


QUICK_PROMPT_DETAILS = {
    "7-day Japan trip under $2,000": ("Japan", 7, 2000, "Culture"),
    "Paris getaway for 5 days": ("Paris", 5, 1800, "Culture"),
    "Dubai weekend escape": ("Dubai", 3, 1500, "Relaxing"),
    "10-day Bali backpacking trip": ("Bali", 10, 1600, "Adventure"),
    "London city break for 4 days": ("London", 4, 1800, "Culture"),
    "Singapore family trip for 5 days": ("Singapore", 5, 2200, "Family"),
    "New York trip for 7 days": ("New York", 7, 2500, "Culture"),
    "Istanbul cultural trip for 5 days": ("Istanbul", 5, 1600, "Culture"),
}


def set_trip_query(query: str) -> None:
    st.session_state["trip_query"] = query
    details = QUICK_PROMPT_DETAILS.get(query)
    if details:
        destination, duration, budget, style = details
        st.session_state["destination"] = destination
        st.session_state["duration_days"] = duration
        st.session_state["trip_budget"] = float(budget)
        st.session_state["travel_style"] = style


def start_new_trip() -> None:
    st.session_state["editing_trip_id"] = None
    st.session_state["destination"] = ""
    st.session_state["departure_iata"] = "DAC"
    st.session_state["arrival_iata"] = ""
    st.session_state["trip_start_date"] = date.today() + timedelta(days=30)
    st.session_state["travelers"] = 2
    st.session_state["duration_days"] = 7
    st.session_state["trip_budget"] = 2000.0
    st.session_state["currency"] = "USD"
    st.session_state["travel_style"] = "Culture"
    st.session_state["trip_query"] = ""
    st.session_state.pop("last_trip_result", None)


default_values = {
    "destination": "",
    "departure_iata": "DAC",
    "arrival_iata": "",
    "trip_start_date": date.today() + timedelta(days=30),
    "travelers": 2,
    "duration_days": 7,
    "trip_budget": 2000.0,
    "currency": "USD",
    "travel_style": "Culture",
    "trip_query": "",
    "editing_trip_id": None,
}
for key, value in default_values.items():
    if key not in st.session_state:
        st.session_state[key] = value

with st.sidebar:
    st.markdown("<div class='sidebar-brand'>🌍 Wayfarer AI</div>", unsafe_allow_html=True)
    st.caption("Your personal AI travel planner")
    st.divider()
    thread_id = st.text_input(
        "Travel profile",
        value="Sumaya_user",
        key="travel_profile",
        help="This ID keeps your travel history in PostgreSQL.",
    )

    history_rows = []
    try:
        initialize_trip_history()
        history_rows = list_user_trips(thread_id)
    except (psycopg.Error, RuntimeError) as error:
        st.error(f"Could not load saved trips: {error}")

    if history_rows:
        st.markdown("<div class='sidebar-kicker'>Saved trips</div>", unsafe_allow_html=True)
        history_labels = {
            row["id"]: (
                f"{row['destination']} · {row['start_date']:%b %d, %Y} "
                f"· {row['duration_days']} days"
            )
            for row in history_rows
        }
        selected_trip_id = st.selectbox(
            "Choose a saved trip",
            options=[row["id"] for row in history_rows],
            format_func=lambda trip_id: history_labels[trip_id],
            key="selected_history_trip",
            label_visibility="collapsed",
        )
        if st.button("Load trip to edit", width="stretch"):
            try:
                saved_trip = get_trip(thread_id, selected_trip_id)
                if saved_trip is None:
                    st.warning("That saved trip is no longer available.")
                else:
                    st.session_state["destination"] = saved_trip["destination"]
                    st.session_state["departure_iata"] = saved_trip["departure_iata"]
                    st.session_state["arrival_iata"] = saved_trip["arrival_iata"]
                    st.session_state["trip_start_date"] = saved_trip["start_date"]
                    st.session_state["travelers"] = saved_trip["travelers"]
                    st.session_state["duration_days"] = saved_trip["duration_days"]
                    st.session_state["trip_budget"] = saved_trip["budget"]
                    st.session_state["currency"] = saved_trip["currency"]
                    st.session_state["travel_style"] = saved_trip["travel_style"]
                    st.session_state["trip_query"] = saved_trip["trip_request"]
                    st.session_state["editing_trip_id"] = saved_trip["id"]
                    st.session_state["last_trip_result"] = saved_trip
                    st.rerun()
            except (psycopg.Error, RuntimeError) as error:
                st.error(f"Could not open that saved trip: {error}")

        with st.expander("Recent trip history"):
            for row in history_rows:
                st.caption(
                    f"**{row['destination']}** — {row['start_date']:%b %d, %Y}, "
                    f"{row['travel_style']}"
                )

    if st.session_state["editing_trip_id"] is not None:
        st.button(
            "＋ Start a new trip",
            on_click=start_new_trip,
            width="stretch",
        )

    st.markdown("<div class='sidebar-kicker'>Your planning team</div>", unsafe_allow_html=True)
    for item in (
        "✈️  Flight research",
        "🏨  Hotel discovery",
        "🗓️  Itinerary design",
        "✨  Final trip plan",
    ):
        st.markdown(f"<div class='sidebar-chip'>{item}</div>", unsafe_allow_html=True)
    st.markdown("<div class='sidebar-kicker'>Powered by</div>", unsafe_allow_html=True)
    st.caption("LangGraph · Groq · PostgreSQL")
    st.caption("Tavily Search · AviationStack")

st.markdown(
    """
    <div class="topbar">
        <div class="topbar-brand">✈️ Wayfarer <span style="color:#176b52">AI</span></div>
        <div class="topbar-note">YOUR NEXT JOURNEY STARTS HERE</div>
    </div>
    <section class="hero">
        <div class="hero-copy">
            <div class="hero-eyebrow">Thoughtful trips, made simple</div>
            <h1 class="hero-title">Go somewhere<br>that moves you.</h1>
            <p class="hero-description">
                Tell us what you have in mind. Your AI travel team will bring together
                flight research, hotel ideas, and a day-by-day itinerary.
            </p>
        </div>
    </section>
    """,
    unsafe_allow_html=True,
)

st.markdown("<h2 class='section-heading'>Find your kind of somewhere</h2>", unsafe_allow_html=True)
st.markdown(
    "<p class='section-caption'>A little inspiration for your next escape.</p>",
    unsafe_allow_html=True,
)

destinations = [
    ("🇯🇵 Tokyo", "https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?w=480&q=75"),
    ("🇫🇷 Paris", "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?w=480&q=75"),
    ("🇹🇭 Bangkok", "https://images.unsplash.com/photo-1508009603885-50cf7c579365?w=480&q=75"),
    ("🇮🇹 Rome", "https://images.unsplash.com/photo-1552832230-c0197dd311b5?w=480&q=75"),
    ("🇦🇪 Dubai", "https://images.unsplash.com/photo-1512453979798-5ea266f8880c?w=480&q=75"),
    ("🇮🇩 Bali", "https://images.unsplash.com/photo-1537996194471-e657df975ab4?w=480&q=75"),
    ("🇬🇧 London", "https://images.unsplash.com/photo-1513635269975-59663e0ac1ad?w=480&q=75"),
    ("🇸🇬 Singapore", "https://images.unsplash.com/photo-1525625293386-3f8f99389edd?w=480&q=75"),
    ("🇺🇸 New York", "https://images.unsplash.com/photo-1534430480872-3498386e7856?w=480&q=75"),
    ("🇹🇷 Istanbul", "https://images.unsplash.com/photo-1524231757912-21f4fe3a7200?w=480&q=75"),
]

def select_destination(label: str) -> None:
    destination = label.split(" ", 1)[1]
    st.session_state["destination"] = destination
    st.session_state["trip_query"] = f"Plan a trip to {destination}."


for start in range(0, len(destinations), 4):
    columns = st.columns(4)
    for column, (name, image_url) in zip(columns, destinations[start : start + 4]):
        with column:
            st.markdown(
                f"""
                <div class="destination-card">
                    <img src="{image_url}" alt="{name.split(' ', 1)[1]}">
                    <div class="destination-shade"></div>
                    <div class="destination-name">{name}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.button(
                f"Plan {name}",
                key=f"destination_{name}",
                on_click=select_destination,
                args=(name,),
                width="stretch",
            )

st.markdown("<br>", unsafe_allow_html=True)

with st.container(border=True):
    st.markdown("<h2 class='form-heading'>Plan a trip that feels like yours</h2>", unsafe_allow_html=True)
    st.markdown(
        "<p class='form-caption'>Add a few trip details, then customize anything you like.</p>",
        unsafe_allow_html=True,
    )

    st.text_input(
        "Where do you want to go?",
        key="destination",
        placeholder="City or country, for example Tokyo",
    )
    airport_columns = st.columns(2)
    with airport_columns[0]:
        st.text_input(
            "Departure airport (IATA)",
            key="departure_iata",
            help="Three-letter airport code; DAC is the default for Dhaka.",
        )
    with airport_columns[1]:
        st.text_input(
            "Arrival airport (IATA)",
            key="arrival_iata",
            placeholder="For example, CDG for Paris",
            help="Enter the three-letter airport code for your destination.",
        )
    travel_columns = st.columns(3)
    with travel_columns[0]:
        st.date_input(
            "Departure date",
            key="trip_start_date",
            min_value=None,
            help="Weather forecasts are available for dates in the next 16 days.",
        )
    with travel_columns[1]:
        st.number_input(
            "Travelers",
            min_value=1,
            max_value=20,
            step=1,
            key="travelers",
        )
    with travel_columns[2]:
        st.number_input(
            "Trip length (days)",
            min_value=1,
            max_value=30,
            step=1,
            key="duration_days",
        )

    budget_columns = st.columns(3)
    with budget_columns[0]:
        st.number_input(
            "Total budget",
            min_value=0.0,
            step=100.0,
            key="trip_budget",
        )
    with budget_columns[1]:
        st.selectbox(
            "Currency",
            options=["USD", "BDT", "INR", "EUR", "GBP", "JPY", "AED"],
            key="currency",
        )
    with budget_columns[2]:
        st.selectbox(
            "Travel style",
            options=["Culture", "Family", "Adventure", "Relaxing", "Food", "Budget"],
            key="travel_style",
        )

    st.markdown("<div class='sidebar-kicker'>Start with an idea</div>", unsafe_allow_html=True)
    quick_prompts = list(QUICK_PROMPT_DETAILS)
    for start in range(0, len(quick_prompts), 4):
        columns = st.columns(4)
        for column, prompt in zip(columns, quick_prompts[start : start + 4]):
            with column:
                st.button(
                    prompt,
                    key=f"quick_{start}_{prompt}",
                    on_click=set_trip_query,
                    args=(prompt,),
                )

    user_query = st.text_area(
        "Anything else we should know?",
        key="trip_query",
        placeholder=(
            "Add preferences like food, accessibility, must-see places, "
            "or a special occasion."
        ),
        height=100,
    )
    generate = st.button(
        "✨  Update saved trip" if st.session_state["editing_trip_id"] else "✨  Build my travel plan",
        type="primary",
        width="stretch",
    )

if generate:
    destination = st.session_state["destination"].strip()
    start_date = st.session_state["trip_start_date"]
    travelers = int(st.session_state["travelers"])
    duration_days = int(st.session_state["duration_days"])
    budget = float(st.session_state["trip_budget"])
    currency = st.session_state["currency"]
    travel_style = st.session_state["travel_style"]
    departure_iata = st.session_state["departure_iata"].strip().upper()
    arrival_iata = st.session_state["arrival_iata"].strip().upper()

    if not destination:
        st.warning("Choose or enter a destination before building your plan.")
    elif start_date < date.today():
        st.warning("Choose a departure date that is today or later.")
    else:
        trip_details = (
            f"Destination: {destination}\n"
            f"Flight route: {departure_iata or 'not provided'} to "
            f"{arrival_iata or 'not provided'}\n"
            f"Departure date: {start_date.isoformat()}\n"
            f"Travelers: {travelers}\n"
            f"Duration: {duration_days} days\n"
            f"Total budget: {budget:,.2f} {currency}\n"
            f"Travel style: {travel_style}\n"
            f"Additional preferences: {user_query.strip() or 'None provided'}"
        )
        agent_request = (
            f"Plan this trip using the exact details below.\n\n{trip_details}\n\n"
            "Create one itinerary day for each trip day. Include a morning, "
            "afternoon, and evening activity for every day. Estimate costs in "
            f"{currency} and label them as estimates, not live quotes."
        )
        config = {"configurable": {"thread_id": thread_id}}
        collected = {
            "flight_results": "",
            "hotel_results": "",
            "itinerary": "",
            "final_response": "",
            "llm_calls": 0,
        }

        st.markdown(
            "<h2 class='results-heading'>Your travel team is at work</h2>",
            unsafe_allow_html=True,
        )
        agent_meta = {
            "flight_agent": ("✈️", "Flight research"),
            "hotel_agent": ("🏨", "Hotel discovery"),
            "itinerary_agent": ("🗓️", "Itinerary design"),
            "final_agent": ("✨", "Final trip plan"),
        }

        for chunk in app.stream(
            {
                "messages": [HumanMessage(content=agent_request)],
                "user_query": agent_request,
                "departure_iata": departure_iata,
                "arrival_iata": arrival_iata,
                "flight_date": start_date,
                "flight_results": "",
                "hotel_results": "",
                "itinerary": "",
                "llm_calls": 0,
            },
            config=config,
            stream_mode="updates",
        ):
            for node_name, state_update in chunk.items():
                icon, label = agent_meta.get(node_name, ("🔧", node_name))
                with st.status(f"{icon}  {label}", state="complete", expanded=True):
                    if node_name == "flight_agent":
                        text = state_update.get("flight_results", "")
                        collected["flight_results"] = text
                        st.markdown(text or "_No flight data returned._")
                    elif node_name == "hotel_agent":
                        text = state_update.get("hotel_results", "")
                        collected["hotel_results"] = text
                        st.markdown(text or "_No hotel data returned._")
                    elif node_name == "itinerary_agent":
                        text = state_update.get("itinerary", "")
                        collected["itinerary"] = text
                        st.markdown(text or "_No itinerary generated._")
                    elif node_name == "final_agent":
                        messages = state_update.get("messages", [])
                        text = messages[-1].content if messages else ""
                        collected["final_response"] = text
                        st.markdown(text or "_No final response._")

                    collected["llm_calls"] = state_update.get(
                        "llm_calls", collected["llm_calls"]
                    )

        coordinates = None
        map_points = []
        unresolved_places = []
        weather_result = {"available": False, "message": "", "days": []}
        try:
            map_points, unresolved_places = resolve_itinerary_locations(
                destination,
                collected["itinerary"],
            )
            coordinates = map_points[0] if map_points else None
        except (requests.RequestException, LookupError, ValueError, KeyError) as error:
            weather_result["message"] = f"Map locations could not be loaded: {error}"

        if coordinates:
            try:
                weather_result = fetch_weather_forecast(
                    coordinates["latitude"],
                    coordinates["longitude"],
                    start_date,
                    duration_days,
                )
            except (requests.RequestException, ValueError, KeyError) as error:
                weather_result["message"] = f"Weather forecast could not be loaded: {error}"

        budget_rows = calculate_budget_breakdown(budget)
        trip_result = {
            "user_id": thread_id,
            "destination": destination,
            "departure_iata": departure_iata,
            "arrival_iata": arrival_iata,
            "start_date": start_date,
            "travelers": travelers,
            "duration_days": duration_days,
            "budget": budget,
            "currency": currency,
            "travel_style": travel_style,
            "trip_request": user_query.strip(),
            "flight_results": collected["flight_results"],
            "hotel_results": collected["hotel_results"],
            "itinerary": collected["itinerary"],
            "final_response": collected["final_response"],
            "weather": weather_result["days"],
            "weather_message": weather_result["message"],
            "map_points": map_points,
            "unresolved_places": unresolved_places,
            "latitude": coordinates["latitude"] if coordinates else None,
            "longitude": coordinates["longitude"] if coordinates else None,
            "llm_calls": collected["llm_calls"],
        }
        try:
            saved_id = save_trip(
                trip_result,
                st.session_state.get("editing_trip_id"),
            )
            trip_result["id"] = saved_id
            st.success("Trip saved to your PostgreSQL history.")
        except (psycopg.Error, RuntimeError, LookupError) as error:
            st.error(f"Your plan was generated, but could not be saved: {error}")
        st.session_state["last_trip_result"] = trip_result

if "last_trip_result" in st.session_state:
    trip_result = st.session_state["last_trip_result"]
    budget_rows = (
        calculate_budget_breakdown(
            trip_result["budget"]
        )
        if trip_result["budget"] > 0
        else []
    )
    st.markdown(
        "<h2 class='results-heading'>Your trip, thoughtfully planned</h2>",
        unsafe_allow_html=True,
    )
    if trip_result.get("final_response"):
        with st.container(border=True):
            st.markdown(trip_result["final_response"])

    plan_tabs = st.tabs(["Day-by-day plan", "Budget", "Map & weather", "Research"])
    with plan_tabs[0]:
        itinerary = trip_result.get("itinerary", "")
        sections = re.split(r"(?m)(?=^#{1,3}\s*Day\s+\d+\b)", itinerary.strip())
        day_count = 0
        for section in sections:
            if not section.strip():
                continue
            heading_match = re.match(r"(?m)^#{1,3}\s*(Day\s+\d+.*)$", section)
            if heading_match:
                day_count += 1
                title = heading_match.group(1).strip()
                content = section[heading_match.end() :].strip()
                with st.expander(title, expanded=day_count == 1):
                    st.markdown(content)
            else:
                st.markdown(section)
        if not day_count and not itinerary:
            st.info("The itinerary was not returned for this trip.")

    with plan_tabs[1]:
        if budget_rows:
            st.caption(
                "Planning estimates only—not supplier quotes. Actual costs vary "
                "by destination, dates, and availability."
            )
            budget_table = pd.DataFrame(budget_rows).rename(
                columns={"category": "Category", "share": "Share", "estimate": "Estimate"}
            )
            budget_table["Estimate"] = budget_table["Estimate"].map(
                lambda amount: f"{trip_result['currency']} {amount:,.2f}"
            )
            st.dataframe(budget_table, hide_index=True, width="stretch")
            st.bar_chart(
                pd.DataFrame(
                    {
                        "Estimated amount": [row["estimate"] for row in budget_rows],
                    },
                    index=[row["category"] for row in budget_rows],
                )
            )
        else:
            st.info("Add a budget to see a category-by-category estimate.")

    with plan_tabs[2]:
        map_points = trip_result.get("map_points", [])
        if map_points:
            st.caption(f"Destination and itinerary places · {trip_result['destination']}")
            st.map(
                pd.DataFrame(
                    [
                        {
                            "lat": point["latitude"],
                            "lon": point["longitude"],
                            "name": point["name"],
                        }
                        for point in map_points
                    ]
                ),
                zoom=10,
                width="stretch",
            )
            st.caption("Mapped places: " + ", ".join(point["name"] for point in map_points))
            if trip_result.get("unresolved_places"):
                st.info(
                    "Could not find map coordinates for: "
                    + ", ".join(trip_result["unresolved_places"])
                )
        else:
            st.info("Map locations are not available for this destination.")

        weather_days = trip_result.get("weather", [])
        if weather_days:
            st.markdown("#### Daily weather forecast")
            weather_table = pd.DataFrame(weather_days).rename(
                columns={
                    "date": "Date",
                    "condition": "Conditions",
                    "high_c": "High °C",
                    "low_c": "Low °C",
                    "rain_chance": "Rain chance %",
                }
            )
            st.dataframe(weather_table, hide_index=True, width="stretch")
            st.caption("Weather source: Open-Meteo. Forecasts are limited to the next 16 days.")
        if trip_result.get("weather_message"):
            st.info(trip_result["weather_message"])

    with plan_tabs[3]:
        st.markdown("#### Flight research")
        st.markdown(trip_result.get("flight_results") or "_No flight data returned._")
        st.markdown("#### Hotel research")
        st.markdown(trip_result.get("hotel_results") or "_No hotel data returned._")

    generated_at = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_stem = f"travel_plan_{trip_result.get('id', generated_at)}"
    details_for_export = (
        f"Destination: {trip_result['destination']}\n"
        f"Flight route: {trip_result.get('departure_iata', 'DAC')} to "
        f"{trip_result.get('arrival_iata') or 'not provided'}\n"
        f"Departure date: {trip_result['start_date']:%Y-%m-%d}\n"
        f"Travelers: {trip_result['travelers']}\n"
        f"Duration: {trip_result['duration_days']} days\n"
        f"Budget: {trip_result['budget']:,.2f} {trip_result['currency']}\n"
        f"Travel style: {trip_result['travel_style']}\n"
        f"Preferences: {trip_result.get('trip_request') or 'None provided'}"
    )
    pdf_data = create_trip_pdf(
        f"{trip_result['destination']} Travel Plan",
        details_for_export,
        trip_result.get("itinerary", ""),
        budget_rows,
        trip_result["currency"],
        trip_result.get("weather", []),
        trip_result.get("final_response", ""),
    )
    download_columns = st.columns(2)
    with download_columns[0]:
        st.download_button(
            "⬇️ Download PDF",
            data=pdf_data,
            file_name=f"{file_stem}.pdf",
            mime="application/pdf",
            width="stretch",
        )
    with download_columns[1]:
        markdown_data = f"""# {trip_result['destination']} Travel Plan

{details_for_export}

## Itinerary
{trip_result.get('itinerary') or 'N/A'}

## Estimated budget
{chr(10).join(f"- {row['category']}: {trip_result['currency']} {row['estimate']:,.2f} ({row['share']})" for row in budget_rows) or 'No budget provided'}

## Weather
{chr(10).join(f"- {day['date']}: {day['condition']}, {day['low_c']}–{day['high_c']} °C" for day in trip_result.get('weather', [])) or trip_result.get('weather_message', 'No forecast available')}

## Final plan
{trip_result.get('final_response') or 'N/A'}
"""
        st.download_button(
            "⬇️ Download Markdown",
            data=markdown_data,
            file_name=f"{file_stem}.md",
            mime="text/markdown",
            width="stretch",
        )
