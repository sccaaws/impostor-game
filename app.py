from flask import Flask, render_template, request, redirect, session, url_for
import random

app = Flask(__name__)
app.secret_key = "change-this-secret-key"

WORDS = {
    "Food": ["Pizza", "Sushi", "Burger", "Pasta", "Taco", "Ice Cream"],
    "Animals": ["Elephant", "Tiger", "Dolphin", "Penguin", "Giraffe", "Wolf"],
    "Places": ["Beach", "Airport", "Museum", "Library", "Restaurant", "School"],
    "Jobs": ["Doctor", "Teacher", "Chef", "Pilot", "Farmer", "Designer"],
}


def create_game(player_count: int, category: str) -> dict:
    players = [
        {"id": i, "name": f"Player {i}", "vote": None}
        for i in range(1, player_count + 1)
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
    }


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        player_count = int(request.form["player_count"])
        category = request.form["category"]

        if player_count < 3 or player_count > 12:
            return render_template(
                "index.html",
                categories=WORDS.keys(),
                error="Choose between 3 and 12 players.",
            )

        session["game"] = create_game(player_count, category)
        return redirect(url_for("reveal", player_number=1))

    return render_template("index.html", categories=WORDS.keys(), error=None)


@app.route("/reveal/<int:player_number>")
def reveal(player_number: int):
    game = session.get("game")
    if not game:
        return redirect(url_for("index"))

    if player_number > game["player_count"]:
        return redirect(url_for("clues"))

    is_impostor = player_number == game["impostor_id"]
    return render_template(
        "reveal.html",
        player_number=player_number,
        is_impostor=is_impostor,
        secret_word=game["secret_word"],
        total_players=game["player_count"],
    )


@app.route("/next_reveal/<int:player_number>", methods=["POST"])
def next_reveal(player_number: int):
    game = session.get("game")
    if not game:
        return redirect(url_for("index"))

    next_player = player_number + 1
    game["current_reveal"] = next_player
    session["game"] = game
    return redirect(url_for("reveal", player_number=next_player))


@app.route("/clues")
def clues():
    game = session.get("game")
    if not game:
        return redirect(url_for("index"))
    return render_template("clues.html", players=game["players"])


@app.route("/start_voting", methods=["POST"])
def start_voting():
    game = session.get("game")
    if not game:
        return redirect(url_for("index"))

    game["current_vote"] = 1
    session["game"] = game
    return redirect(url_for("vote", voter_number=1))


@app.route("/vote/<int:voter_number>", methods=["GET", "POST"])
def vote(voter_number: int):
    game = session.get("game")
    if not game:
        return redirect(url_for("index"))

    if request.method == "POST":
        voted_for = int(request.form["voted_for"])
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
        total_players=game["player_count"],
        players=game["players"],
    )


@app.route("/count_votes")
def count_votes():
    game = session.get("game")
    if not game:
        return redirect(url_for("index"))

    tally = {}
    for player in game["players"]:
        vote = player["vote"]
        tally[vote] = tally.get(vote, 0) + 1

    accused_id = max(tally, key=tally.get)
    game["accused_id"] = accused_id
    session["game"] = game

    if accused_id == game["impostor_id"]:
        return redirect(url_for("guess_word"))

    game["winner"] = "Crewmates"
    session["game"] = game
    return redirect(url_for("results"))


@app.route("/guess", methods=["GET", "POST"])
def guess_word():
    game = session.get("game")
    if not game:
        return redirect(url_for("index"))

    if request.method == "POST":
        guess = request.form["guess"].strip().lower()
        if guess == game["secret_word"].lower():
            game["winner"] = "Impostor"
        else:
            game["winner"] = "Crewmates"
        session["game"] = game
        return redirect(url_for("results"))

    return render_template("guess.html")


@app.route("/results")
def results():
    game = session.get("game")
    if not game:
        return redirect(url_for("index"))

    return render_template(
        "results.html",
        winner=game["winner"],
        secret_word=game["secret_word"],
        impostor_id=game["impostor_id"],
        accused_id=game["accused_id"],
    )


@app.route("/reset", methods=["POST"])
def reset():
    session.pop("game", None)
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
