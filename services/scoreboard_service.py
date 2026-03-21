from flask import session


def create_scoreboard(player_names: list[str]) -> dict:
    return {
        "rounds_played": 0,
        "crewmate_wins": 0,
        "impostor_wins": 0,
        "player_stats": [
            {
                "name": name,
                "wins": 0,
                "times_impostor": 0,
                "times_accused": 0,
                "correct_votes": 0,
            }
            for name in player_names
        ],
    }


def update_scoreboard_if_needed(game: dict):
    if game.get("score_updated"):
        return

    scoreboard = session.get("scoreboard")
    if not scoreboard or not game.get("winner"):
        return

    scoreboard["rounds_played"] += 1

    if game["winner"] == "Crewmates":
        scoreboard["crewmate_wins"] += 1
    elif game["winner"] == "Impostor":
        scoreboard["impostor_wins"] += 1

    impostor_player = game["players"][game["impostor_id"] - 1]
    impostor_name = impostor_player["name"]

    accused_id = game.get("accused_id")
    accused_name = None
    if accused_id is not None:
        accused_name = next(
            (player["name"] for player in game["players"] if player["id"] == accused_id),
            None
        )

    # Track accusations by player name
    if accused_name is not None:
        for stat in scoreboard["player_stats"]:
            if stat["name"] == accused_name:
                stat["times_accused"] += 1
                break

    # Track correct votes by voter name
    for player in game["players"]:
        voted_for = player.get("vote")
        if voted_for == game["impostor_id"]:
            for stat in scoreboard["player_stats"]:
                if stat["name"] == player["name"]:
                    stat["correct_votes"] += 1
                    break

    # Track wins by player name
    if game["winner"] == "Impostor":
        for stat in scoreboard["player_stats"]:
            if stat["name"] == impostor_name:
                stat["wins"] += 1
                break
    elif game["winner"] == "Crewmates":
        for stat in scoreboard["player_stats"]:
            if stat["name"] != impostor_name:
                stat["wins"] += 1

    session["scoreboard"] = scoreboard
    game["score_updated"] = True
    session["game"] = game