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


def get_categories() -> list[str]:
    return list(WORDS.keys())


def get_difficulties() -> list[str]:
    return ["easy", "hard"]


def get_words_for(category: str, difficulty: str) -> list[str]:
    return WORDS[category][difficulty]


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


def create_scoreboard(player_names: list[str]) -> dict:
    return {
        "rounds_played": 0,
        "crewmate_wins": 0,
        "impostor_wins": 0,
        "player_stats": [
            {
                "id": i + 1,
                "name": player_names[i],
                "times_impostor": 0,
            }
            for i in range(len(player_names))
        ],
    }


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

    session["scoreboard"] = scoreboard
    game["score_updated"] = True
    session["game"] = game


def get_used_words_by_key() -> dict:
    return session.get("used_words_by_key", {})


def save_used_word(category: str, difficulty: str, word: str):
    used_words_by_key = get_used_words_by_key()
    key = f"{category}:{difficulty}"
    used_words = used_words_by_key.get(key, [])

    used_words.append(word)
    used_words = used_words[-5:]

    used_words_by_key[key] = used_words
    session["used_words_by_key"] = used_words_by_key


def choose_secret_word(category: str, difficulty: str) -> str:
    all_words = get_words_for(category, difficulty)
    used_words_by_key = get_used_words_by_key()
    key = f"{category}:{difficulty}"
    used_words = used_words_by_key.get(key, [])

    available_words = [word for word in all_words if word not in used_words]

    if not available_words:
        used_words_by_key[key] = []
        session["used_words_by_key"] = used_words_by_key
        available_words = all_words[:]

    secret_word = random.choice(available_words)
    save_used_word(category, difficulty, secret_word)
    return secret_word


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            player_count = int(request.form["player_count"])
            difficulty = request.form.get("difficulty", "easy")

            if difficulty not in get_difficulties():
                return render_template(
                    "index.html",
                    categories=get_categories(),
                    error="Choose a valid difficulty.",
                )
        except (KeyError, ValueError):
            return render_template(
                "index.html",
                categories=get_categories(),
                error="Enter a valid number of players.",
            )

        category = request.form.get("category", "Food")

        if player_count < 3 or player_count > 12:
            return render_template(
                "index.html",
                categories=get_categories(),
                error="Choose between 3 and 12 players.",
            )

        if category not in WORDS:
            return render_template(
                "index.html",
                categories=get_categories(),
                error="Choose a valid category.",
            )

        session["setup"] = {
            "player_count": player_count,
            "category": category,
            "difficulty": difficulty,
        }
        return redirect(url_for("lobby"))

    return render_template("index.html", categories=get_categories(), error=None)


@app.route("/lobby", methods=["GET", "POST"])
def lobby():
    setup = session.get("setup")
    if not setup:
        return redirect(url_for("index"))

    player_count = setup["player_count"]
    category = setup["category"]

    difficulty = setup["difficulty"]

    if request.method == "POST":
        player_names = []
        for i in range(1, player_count + 1):
            name = request.form.get(f"player_{i}", "").strip()
            if not name:
                name = f"Player {i}"
            player_names.append(name)

        session["cached_player_names"] = player_names
        session["scoreboard"] = create_scoreboard(player_names)
        start_new_round(player_names, category, difficulty)

        session.pop("setup", None)
        return redirect(url_for("reveal", player_number=1))

    cached_or_default_names = get_cached_names(player_count)

    return render_template(
        "lobby.html",
        player_count=player_count,
        category=category,
        difficulty=difficulty,
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


@app.route("/play_again", methods=["POST"])
def play_again():
    game = get_game()
    scoreboard = session.get("scoreboard")

    if not game or not scoreboard:
        return redirect(url_for("index"))

    player_names = [player["name"] for player in game["players"]]
    category = game["category"]
    difficulty = game["difficulty"]

    start_new_round(player_names, category, difficulty)
    return redirect(url_for("reveal", player_number=1))


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


@app.route("/pass/<int:player_number>")
def pass_screen(player_number: int):
    game = get_game()
    if not game:
        return redirect(url_for("index"))

    if player_number > game["player_count"]:
        return redirect(url_for("clues"))

    current_player = game["players"][player_number - 1]

    return render_template(
        "pass.html",
        player_number=player_number,
        player_name=current_player["name"],
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

    return redirect(url_for("pass_screen", player_number=next_player))


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
        difficulty=game["difficulty"],
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
    return redirect(url_for("vote_pass_screen", voter_number=1))


@app.route("/vote_pass/<int:voter_number>")
def vote_pass_screen(voter_number: int):
    game = get_game()
    if not game:
        return redirect(url_for("index"))

    if voter_number > game["player_count"]:
        return redirect(url_for("count_votes"))

    if voter_number != game["current_vote"]:
        return redirect(url_for("vote_pass_screen", voter_number=game["current_vote"]))

    current_voter = game["players"][voter_number - 1]

    return render_template(
        "vote_pass.html",
        voter_number=voter_number,
        voter_name=current_voter["name"],
        total_players=game["player_count"],
    )


@app.route("/vote/<int:voter_number>", methods=["GET", "POST"])
def vote(voter_number: int):
    game = get_game()
    if not game:
        return redirect(url_for("index"))

    if voter_number != game["current_vote"]:
        return redirect(url_for("vote_pass_screen", voter_number=game["current_vote"]))

    current_voter = game["players"][voter_number - 1]

    if request.method == "POST":
        try:
            voted_for = int(request.form["voted_for"])
        except (KeyError, ValueError):
            eligible_players = [
                player
                for player in game["players"]
                if player["id"] != current_voter["id"]
            ]
            return render_template(
                "vote.html",
                voter_number=voter_number,
                voter_name=current_voter["name"],
                total_players=game["player_count"],
                players=eligible_players,
                error="Choose a valid player.",
            )

        valid_ids = {
            player["id"]
            for player in game["players"]
            if player["id"] != current_voter["id"]
        }

        if voted_for not in valid_ids:
            eligible_players = [
                player
                for player in game["players"]
                if player["id"] != current_voter["id"]
            ]
            return render_template(
                "vote.html",
                voter_number=voter_number,
                voter_name=current_voter["name"],
                total_players=game["player_count"],
                players=eligible_players,
                error="You cannot vote for yourself.",
            )

        return redirect(
            url_for("confirm_vote", voter_number=voter_number, voted_for=voted_for)
        )

    eligible_players = [
        player for player in game["players"] if player["id"] != current_voter["id"]
    ]

    return render_template(
        "vote.html",
        voter_number=voter_number,
        voter_name=current_voter["name"],
        total_players=game["player_count"],
        players=eligible_players,
        error=None,
    )


@app.route("/confirm_vote/<int:voter_number>/<int:voted_for>", methods=["GET", "POST"])
def confirm_vote(voter_number: int, voted_for: int):
    game = get_game()
    if not game:
        return redirect(url_for("index"))

    if voter_number != game["current_vote"]:
        return redirect(url_for("vote_pass_screen", voter_number=game["current_vote"]))

    current_voter = game["players"][voter_number - 1]
    valid_ids = {
        player["id"]
        for player in game["players"]
        if player["id"] != current_voter["id"]
    }

    if voted_for not in valid_ids:
        return redirect(url_for("vote", voter_number=voter_number))

    voted_player = next(
        player for player in game["players"] if player["id"] == voted_for
    )

    if request.method == "POST":
        game["players"][voter_number - 1]["vote"] = voted_for
        next_voter = voter_number + 1
        game["current_vote"] = next_voter
        session["game"] = game

        if next_voter > game["player_count"]:
            return redirect(url_for("count_votes"))

        return redirect(url_for("vote_pass_screen", voter_number=next_voter))

    return render_template(
        "confirm_vote.html",
        voter_number=voter_number,
        voter_name=current_voter["name"],
        voted_player=voted_player,
        total_players=game["player_count"],
    )


@app.route("/count_votes")
def count_votes():
    game = get_game()
    if not game:
        return redirect(url_for("index"))

    votes = [player["vote"] for player in game["players"] if player["vote"] is not None]
    counts = Counter(votes)

    if not counts:
        return redirect(url_for("vote_pass_screen", voter_number=1))

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
        game["winner"] = (
            "Impostor" if guess == game["secret_word"].lower() else "Crewmates"
        )
        session["game"] = game
        return redirect(url_for("results"))

    return render_template("guess.html")


@app.route("/results")
def results():
    game = get_game()
    if not game:
        return redirect(url_for("index"))

    update_scoreboard_if_needed(game)

    return render_template(
        "results.html",
        winner=game["winner"],
        secret_word=game["secret_word"],
        impostor_id=game["impostor_id"],
        accused_id=game["accused_id"],
        vote_result=game["vote_result"],
        players=game["players"],
        scoreboard=session.get("scoreboard"),
    )


@app.route("/reset", methods=["POST"])
def reset():
    session.pop("game", None)
    session.pop("setup", None)
    session.pop("scoreboard", None)
    session.pop("used_words_by_key", None)
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
