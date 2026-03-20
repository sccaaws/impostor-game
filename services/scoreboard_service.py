from flask import session


def create_scoreboard(player_names: list[str]) -> dict:
    return {
        "rounds_played": 0,
        "crewmate_wins": 0,
        "impostor_wins": 0,
        "player_stats": [
            {
                "id": i + 1,
                "name": player_names[i],
                "wins": 0,
                "times_impostor": 0,
                "times_accused": 0,
                "correct_votes": 0,
            }
            for i in range(len(player_names))
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

    impostor_id = game["impostor_id"]
    accused_id = game.get("accused_id")

    if accused_id is not None:
        for stat in scoreboard["player_stats"]:
            if stat["id"] == accused_id:
                stat["times_accused"] += 1
                break

    for player in game["players"]:
        if player.get("vote") == impostor_id:
            for stat in scoreboard["player_stats"]:
                if stat["id"] == player["id"]:
                    stat["correct_votes"] += 1
                    break

    if game["winner"] == "Impostor":
        for stat in scoreboard["player_stats"]:
            if stat["id"] == impostor_id:
                stat["wins"] += 1
                break
    elif game["winner"] == "Crewmates":
        for stat in scoreboard["player_stats"]:
            if stat["id"] != impostor_id:
                stat["wins"] += 1

    session["scoreboard"] = scoreboard
    game["score_updated"] = True
    session["game"] = game
