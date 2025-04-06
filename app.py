
import streamlit as st
import requests
import gspread
from datetime import datetime

import os
from dotenv import load_dotenv

load_dotenv()  # Load the .env file

API_KEY = os.getenv("API_FOOTBALL_KEY")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SERVICE_ACCOUNT_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH")

BASE_URL = "https://v3.football.api-sports.io"
headers = {"x-apisports-key": API_KEY}

LEAGUES = {
    "Premier League": 39,
    "La Liga": 140,
    "Bundesliga": 78,
    "Ligue 1": 61,
    "Serie A": 135,
    "Champions League": 2,
    "Europa League": 3,
    "Conference League": 848,
    "Brazil Série A": 71,
    "Brazil Série B": 72
}

STAR_PLAYERS = {
    "Flamengo": ["Pedro", "Gabriel Barbosa", "De Arrascaeta"],
    "Palmeiras": ["Endrick", "Raphael Veiga", "Dudu"],
    "Corinthians": ["Yuri Alberto", "Paulinho", "Renato Augusto"],
    "São Paulo": ["Luciano", "Calleri", "Lucas Moura"],
    "Cruzeiro": ["Bruno Rodrigues", "Matheus Pereira", "Rafael Elias"],
    "Vasco da Gama": ["Payet", "Gabriel Pec", "Pablo Vegetti"],
    "Grêmio": ["Luis Suárez", "Cristaldo", "Pepê"],
    "Internacional": ["Alan Patrick", "Enner Valencia", "Carlos de Pena"],
    "Atlético Mineiro": ["Hulk", "Paulinho", "Zaracho"]
}

def calculate_confidence(stat_value, benchmark, direction="over"):
    if stat_value is None or not isinstance(stat_value, int):
        return 50
    delta = stat_value - benchmark
    confidence = 60 + delta * 5 if direction == "over" else 60 - delta * 5
    return max(45, min(confidence, 90))

def kelly_stake(bankroll, odds, confidence):
    p = confidence / 100
    b = odds - 1
    q = 1 - p
    k = ((b * p) - q) / b
    return max(0, bankroll * k), k * 100

def append_multiple_to_sheet(rows):
    try:
        gc = gspread.service_account(filename=SERVICE_ACCOUNT_PATH)
        sh = gc.open_by_key(GOOGLE_SHEET_ID)
        worksheet = sh.sheet1
        for row in rows:
            worksheet.append_row(row)
    except Exception as e:
        st.error(f"Google Sheets error: {e}")

st.title("Smart Betting Assistant (with Brazil & Bankroll Management)")

bankroll = st.number_input("Your Bankroll (R$)", min_value=10.0, value=200.0, step=10.0)
selected_date = st.date_input("Select match date", datetime.today())
selected_league_name = st.selectbox("Select league", list(LEAGUES.keys()))
selected_league_id = LEAGUES[selected_league_name]

@st.cache_data
def get_fixtures(league_id, date):
    url = f"{BASE_URL}/fixtures?league={league_id}&season=2024&date={date}"
    response = requests.get(url, headers=headers)
    matches = []
    if response.status_code == 200:
        for match in response.json()["response"]:
            matches.append({
                "label": f"{match['teams']['home']['name']} vs {match['teams']['away']['name']}",
                "id": match["fixture"]["id"],
                "home": match["teams"]["home"]["name"],
                "away": match["teams"]["away"]["name"]
            })
    return matches

fixtures = get_fixtures(selected_league_id, selected_date.strftime("%Y-%m-%d"))
match_labels = [f["label"] for f in fixtures]

if fixtures:
    selected_match = st.selectbox("Select a match", match_labels)
    match_data = next(f for f in fixtures if f["label"] == selected_match)
    match_id = match_data["id"]

    st.info(f"Match selected: {selected_match}")

    def get_match_stats(fixture_id):
        url = f"{BASE_URL}/fixtures/statistics?fixture={fixture_id}"
        response = requests.get(url, headers=headers)
        return response.json().get("response", [])

    stats = get_match_stats(match_id)

    if stats:
        st.subheader("Live Match Statistics")
        home_stats = stats[0]["statistics"]
        away_stats = stats[1]["statistics"]

        def extract_stat(stats_list, stat_name):
            for stat in stats_list:
                if stat["type"] == stat_name:
                    return stat["value"]
            return None

        home_corners = extract_stat(home_stats, "Corner Kicks")
        away_corners = extract_stat(away_stats, "Corner Kicks")
        home_sot = extract_stat(home_stats, "Shots on Target")
        away_sot = extract_stat(away_stats, "Shots on Target")

        total_corners = (home_corners or 0) + (away_corners or 0)
        total_sot = (home_sot or 0) + (away_sot or 0)

        st.metric("Total Corners", total_corners)
        st.metric("Total SOT", total_sot)

        st.subheader("Suggested Bets")

        select_all = st.checkbox("Select All")

        bets = [
            {"label": "Over 7.5 Shots on Target", "value": total_sot, "benchmark": 7},
            {"label": "Over 9.5 Corners", "value": total_corners, "benchmark": 9},
            {"label": "BTTS or Over 2.5 Goals", "value": None, "benchmark": None, "confidence": 65}
        ]

        selected_bets = []

        for i, bet in enumerate(bets):
            conf = bet.get("confidence") or calculate_confidence(bet["value"], bet["benchmark"])
            col1, col2, col3 = st.columns([4, 2, 3])
            with col1:
                place = st.checkbox(f"{bet['label']} — {conf}% confidence", key=i, value=select_all)
            with col2:
                odds = st.number_input(f"Odds for {bet['label']}", key=f"odds_{i}", min_value=1.01, value=1.85, step=0.01)
            with col3:
                stake, perc = kelly_stake(bankroll, odds, conf)
                st.write(f"Stake: R${stake:.2f} ({perc:.1f}%)")
            if place:
                selected_bets.append([
                    str(datetime.now().date()), selected_match, bet["label"], f"{conf}%", f"{odds:.2f}", f"R${stake:.2f}", ""
                ])

        if selected_bets and st.button("Upload Selected Bets to Sheet"):
            append_multiple_to_sheet(selected_bets)
            st.success(f"{len(selected_bets)} bet(s) uploaded to Google Sheet!")

st.markdown("---")
st.caption("Powered by API-Football, Google Sheets, and Streamlit")
