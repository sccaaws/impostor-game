from flask import Flask, render_template, request, redirect, session, url_for
from collections import Counter
from pathlib import Path
import json
import random

app = Flask(__name__)
app.secret_key = "change-this-secret-key"


def load_words() -> dict:
    words_path = Path(__file__).parent / "words.json"
    with open(words_path, "r", encoding="utf-8") as f:
        return json.load(f)


WORDS = load_words()


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


def create_game(player_names: list[str], category: str) -> dict:
    player_count = len(player_names)
    players = [
        {"id": i + 1, "name": player_names[i].strip(), "vote": None}
        for i in range(player_count)
    ]

    secret_word = random.choice(WORDS[category])
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
    }


def get_game():
    return session.get("game")


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            player_count = int(request.form["player_count"])
        except (KeyError, ValueError):
            return render_template(
                "index.html",
                categories=WORDS.keys(),
                error="Enter a valid number of players.",
            )

        category = request.form.get("category", "Food")

        if player_count < 3 or player_count > 12:
            return render_template(
                "index.html",
                categories=WORDS.keys(),
                error="Choose between 3 and 12 players.",
            )

        if category not in WORDS:
            return render_template(
                "index.html",
                categories=WORDS.keys(),
                error="Choose a valid category.",
            )

        session["setup"] = {
            "player_count": player_count,
            "category": category,
        }
        return redirect(url_for("lobby"))

    return render_template("index.html", categories=WORDS.keys(), error=None)


@app.route("/lobby", methods=["GET", "POST"])
def lobby():
    setup = session.get("setup")
    if not setup:
        return redirect(url_for("index"))

    player_count = setup["player_count"]
    category = setup["category"]

    if request.method == "POST":
        player_names = []
        for i in range(1, player_count + 1):
            name = request.form.get(f"player_{i}", "").strip()
            if not name:
                name = f"Player {i}"
            player_names.append(name)

        session["cached_player_names"] = player_names
        session["game"] = create_game(player_names, category)
        session.pop("setup", None)
        return redirect(url_for("reveal", player_number=1))

    cached_or_default_names = get_cached_names(player_count)

    return render_template(
        "lobby.html",
        player_count=player_count,
        category=category,
        player_names=cached_or_default_names,
    )


@app.route("/reset_names", methods=["POST"])
def reset_names():
    setup = session.get("setup")
    if not setup:
        return redirect(url_for("index"))

    player_count = setup["player_count"]
    session["cached_player_names"] = default_player_names(player_count)
    return redirect(url_for("lobby"))


@app.route("/reveal/<int:player_number>")
def reveal(player_number: int):
    game = get_game()
    if not game:
        return redirect(url_for("index"))

    if player_number != game["current_reveal"]:
        return redirect(url_for("reveal", player_number=game["current_reveal"]))

    if player_number > game["player_count"]:
        return redirect(url_for("clues"))

    current_player = game["players"][player_number - 1]
    is_impostor = player_number == game["impostor_id"]

    return render_template(
        "reveal.html",
        player_number=player_number,
        player_name=current_player["name"],
        is_impostor=is_impostor,
        secret_word=game["secret_word"],
        total_players=game["player_count"],
    )


@app.route("/next_reveal/<int:player_number>", methods=["POST"])
def next_reveal(player_number: int):
    game = get_game()
    if not game:
        return redirect(url_for("index"))

    if player_number != game["current_reveal"]:
        return redirect(url_for("reveal", player_number=game["current_reveal"]))

    next_player = player_number + 1
    game["current_reveal"] = next_player
    session["game"] = game

    if next_player > game["player_count"]:
        return redirect(url_for("clues"))
    return redirect(url_for("reveal", player_number=next_player))


@app.route("/clues")
def clues():
    game = get_game()
    if not game:
        return redirect(url_for("index"))

    if game["current_reveal"] <= game["player_count"]:
        return redirect(url_for("reveal", player_number=game["current_reveal"]))

    return render_template(
        "clues.html",
        players=game["players"],
        category=game["category"],
    )


@app.route("/start_voting", methods=["POST"])
def start_voting():
    game = get_game()
    if not game:
        return redirect(url_for("index"))

    game["current_vote"] = 1
    for player in game["players"]:
        player["vote"] = None

    session["game"] = game
    return redirect(url_for("vote", voter_number=1))


@app.route("/vote/<int:voter_number>", methods=["GET", "POST"])
def vote(voter_number: int):
    game = get_game()
    if not game:
        return redirect(url_for("index"))

    if voter_number != game["current_vote"]:
        return redirect(url_for("vote", voter_number=game["current_vote"]))

    current_voter = game["players"][voter_number - 1]

    if request.method == "POST":
        try:
            voted_for = int(request.form["voted_for"])
        except (KeyError, ValueError):
            return render_template(
                "vote.html",
                voter_number=voter_number,
                voter_name=current_voter["name"],
                total_players=game["player_count"],
                players=game["players"],
                error="Choose a valid player.",
            )

        valid_ids = {player["id"] for player in game["players"]}
        if voted_for not in valid_ids:
            return render_template(
                "vote.html",
                voter_number=voter_number,
                voter_name=current_voter["name"],
                total_players=game["player_count"],
                players=game["players"],
                error="Choose a valid player.",
            )

        game["players"][voter_number - 1]["vote"] = voted_for
        next_voter = voter_number + 1
        game["current_vote"] = next_voter
        session["game"] = game

        if next_voter > game["player_count"]:
            return redirect(url_for("count_votes"))
        return redirect(url_for("vote", voter_number=next_voter))

    return render_template(
        "vote.html",
        voter_number=voter_number,
        voter_name=current_voter["name"],
        total_players=game["player_count"],
        players=game["players"],
        error=None,
    )


@app.route("/count_votes")
def count_votes():
    game = get_game()
    if not game:
        return redirect(url_for("index"))

    votes = [player["vote"] for player in game["players"] if player["vote"] is not None]
    counts = Counter(votes)

    if not counts:
        return redirect(url_for("vote", voter_number=1))

    top_votes = max(counts.values())
    leaders = [player_id for player_id, count in counts.items() if count == top_votes]

    if len(leaders) > 1:
        game["accused_id"] = None
        game["vote_result"] = "tie"
        game["winner"] = "Impostor"
        session["game"] = game
        return redirect(url_for("results"))

    accused_id = leaders[0]
    game["accused_id"] = accused_id
    game["vote_result"] = "caught" if accused_id == game["impostor_id"] else "missed"
    session["game"] = game

    if accused_id == game["impostor_id"]:
        return redirect(url_for("guess_word"))

    game["winner"] = "Impostor"
    session["game"] = game
    return redirect(url_for("results"))


@app.route("/guess", methods=["GET", "POST"])
def guess_word():
    game = get_game()
    if not game:
        return redirect(url_for("index"))

    if game.get("vote_result") != "caught":
        return redirect(url_for("results"))

    if request.method == "POST":
        guess = request.form.get("guess", "").strip().lower()
        game["winner"] = "Impostor" if guess == game["secret_word"].lower() else "Crewmates"
        session["game"] = game
        return redirect(url_for("results"))

    return render_template("guess.html")


@app.route("/results")
def results():
    game = get_game()
    if not game:
        return redirect(url_for("index"))

    return render_template(
        "results.html",
        winner=game["winner"],
        secret_word=game["secret_word"],
        impostor_id=game["impostor_id"],
        accused_id=game["accused_id"],
        vote_result=game["vote_result"],
        players=game["players"],
    )


@app.route("/reset", methods=["POST"])
def reset():
    session.pop("game", None)
    session.pop("setup", None)
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)