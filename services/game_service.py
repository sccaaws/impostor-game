from flask import session
import random
from services.words_service import choose_secret_word


def default_player_names(player_count: int) -> list[str]:
    return [f"Player {i}" for i in range(1, player_count + 1)]


def get_cached_names(player_count: int) -> list[str]:
    cached_names = session.get("cached_player_names", [])
    names = []

    for i in range(player_count):
        if i < len(cached_names) and cached_names[i].strip():
            names.append(cached_names[i].strip())
        else:
            names.append(f"Player {i + 1}")

    return names


def create_game(player_names: list[str], category: str, difficulty: str) -> dict:
    player_count = len(player_names)
    players = [
        {"id": i + 1, "name": player_names[i].strip(), "vote": None}
        for i in range(player_count)
    ]

    secret_word = choose_secret_word(category, difficulty)
    impostor_id = random.randint(1, player_count)

    return {
        "player_count": player_count,
        "category": category,
        "players": players,
        "secret_word": secret_word,
        "impostor_id": impostor_id,
        "current_reveal": 1,
        "current_vote": 1,
        "accused_id": None,
        "winner": None,
        "vote_result": None,
        "score_updated": False,
        "difficulty": difficulty,
    }


def start_new_round(player_names: list[str], category: str, difficulty: str):
    game = create_game(player_names, category, difficulty)
    session["game"] = game

    scoreboard = session.get("scoreboard")
    if scoreboard:
        for player in scoreboard["player_stats"]:
            if player["id"] == game["impostor_id"]:
                player["times_impostor"] += 1
                break
        session["scoreboard"] = scoreboard


def get_game():
    return session.get("game")
