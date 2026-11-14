'''
# pip install langgraph langchain langchain-openai langchain-groq langchain-community langchain-tavily psycopg[binary] psycopg_pool python-dotenv tavily-python pip install requests streamlit

# install PostgresSql and create database
CREATE DATABASE langgraph_memory;  ( or open pgadmin4 and create database there )
'''
# LangGraph Multi-Agent Travel Booking System with Long-Term Memory

# main.py

import os
from datetime import date
from typing import TypedDict, Annotated
import operator

import psycopg
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver
from langchain_core.messages import (
    AnyMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
)

from langchain_groq import ChatGroq

from tools.tavily_tool import tavily_search
from tools.flight_tool import search_flights
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# LLM
llm = ChatGroq(
    model=os.getenv("GROQ_MODEL") or "openai/gpt-oss-120b"
)

# State
class TravelState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    user_query: str
    departure_iata: str
    arrival_iata: str
    flight_date: date
    flight_results: str
    hotel_results: str
    itinerary: str
    llm_calls: int

# Flight Agent
def flight_agent(state: TravelState):
    try:
        flight_data = search_flights(
            state["departure_iata"],
            state["arrival_iata"],
            state["flight_date"],
        )
    except (RuntimeError, ValueError) as error:
        flight_data = f"Flight schedule lookup unavailable: {error}"

    return {
        "flight_results": flight_data,
        "messages": [
            AIMessage(content="Flight schedule search completed")
        ],
        "llm_calls": state.get("llm_calls", 0) + 1
    }

# Hotel Agent
def hotel_agent(state: TravelState):
    query = f"Best hotels for {state['user_query']}"
    hotel_results = tavily_search(query)

    return {
        "hotel_results": hotel_results,
        "messages": [
            AIMessage(content="Hotel information fetched")
        ],
        "llm_calls": state.get("llm_calls", 0) + 1
    }

# Itinerary Agent
def itinerary_agent(state: TravelState):

    prompt = f"""
    Create a practical, day-by-day travel itinerary and budget guidance.
    User Query:
    {state['user_query']}

    Flight Results:
    {state['flight_results']}

    Hotel Results:
    {state['hotel_results']}

    Requirements:
    - Use one Markdown heading per day in the exact format "### Day 1 — Short title".
    - Include a morning, afternoon, and evening suggestion for every requested day.
    - Include practical travel time or transport notes when useful.
    - Add an "Estimated Budget Breakdown" section with flights, accommodation,
      food, local transport, and activities when a total budget was provided.
    - End with a "### Map locations" section listing up to six real, recognizable
      attractions or neighborhoods from the itinerary as "- Place name — Day N".
      Do not invent street addresses or coordinates.
    - Clearly label estimates as estimates; do not present them as live quotes.
    - Do not claim that unverified flight or hotel prices are confirmed bookings.
    - Only describe flight records present in the supplied results; if lookup
      failed or returned no schedules, say so and keep any flight costs labeled
      as estimates.
    - Any live flight matches are route references only; never present them as
      scheduled for the user's future trip date.
    """

    response = llm.invoke([
        SystemMessage(
            content="You are an expert travel planner"
        ),
        HumanMessage(content=prompt)
    ])

    return {
        "itinerary": response.content,
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1
    }

# Final Response Agent
def final_agent(state: TravelState):

    final_prompt = f"""
    Write a concise, useful final travel plan based on the supplied research.

    Flights:
    {state['flight_results']}

    Hotels:
    {state['hotel_results']}

    Itinerary:
    {state['itinerary']}

    Keep the itinerary day-by-day, preserve the trip dates, budget, party size,
    and travel style from the user's request, and distinguish estimates from
    verified search results. Live flight matches are route references only and
    are not schedules for the user's trip date. Never imply that anything has
    been booked.
    """

    response = llm.invoke([
        HumanMessage(content=final_prompt)
    ])

    return {
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1
    }


graph = StateGraph(TravelState)

graph.add_node("flight_agent", flight_agent)
graph.add_node("hotel_agent", hotel_agent)
graph.add_node("itinerary_agent", itinerary_agent)
graph.add_node("final_agent", final_agent)

graph.add_edge(START, "flight_agent")
graph.add_edge("flight_agent", "hotel_agent")
graph.add_edge("hotel_agent", "itinerary_agent")
graph.add_edge("itinerary_agent", "final_agent")
graph.add_edge("final_agent", END)


# Persistent connection so both CLI and Streamlit can share the compiled app
_conn = psycopg.connect(DATABASE_URL, autocommit=True)
checkpointer = PostgresSaver(_conn)
checkpointer.setup()

app = graph.compile(checkpointer=checkpointer)


if __name__ == "__main__":
    config = {
        "configurable": {
            "thread_id": "user_Sumaya"
        }
    }

    user_input = input("Enter travel request: ")
    departure_iata = input("Departure airport IATA code [DAC]: ").strip() or "DAC"
    arrival_iata = input("Arrival airport IATA code: ").strip()
    flight_date = date.fromisoformat(input("Departure date (YYYY-MM-DD): ").strip())

    result = app.invoke(
        {
            "messages": [
                HumanMessage(content=user_input)
            ],
            "user_query": user_input,
            "departure_iata": departure_iata,
            "arrival_iata": arrival_iata,
            "flight_date": flight_date,
            "flight_results": "",
            "hotel_results": "",
            "itinerary": "",
            "llm_calls": 0
        },
        config=config
    )

    print("\nFINAL RESPONSE:\n")

    for msg in result["messages"]:
        print(msg.content)