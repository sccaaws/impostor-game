from collections import Counter
from flask import render_template, request, redirect, session, url_for

from services.options_service import get_options
from services.words_service import get_categories, get_difficulties, WORDS
from services.scoreboard_service import create_scoreboard, update_scoreboard_if_needed
from services.game_service import (
    default_player_names,
    get_cached_names,
    start_new_round,
    get_game,
)


def register_routes(app):
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

            existing_scoreboard = session.get("scoreboard")
            existing_names = (
                [stat["name"] for stat in existing_scoreboard["player_stats"]]
                if existing_scoreboard
                else None
            )

            if existing_names != player_names:
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

        category = request.form.get("category", game["category"])
        difficulty = request.form.get("difficulty", game["difficulty"])

        if category not in get_categories():
            category = game["category"]

        if difficulty not in get_difficulties():
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

        if player_number != game["current_reveal"]:
            return redirect(
                url_for("pass_screen", player_number=game["current_reveal"])
            )

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
        game["accused_id"] = None
        game["vote_result"] = None

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
            return redirect(
                url_for("vote_pass_screen", voter_number=game["current_vote"])
            )

        current_voter = game["players"][voter_number - 1]

        return render_template(
            "vote_pass.html",
            voter_number=voter_number,
            voter_name=current_voter["name"],
            total_players=game["player_count"],
            game=game,
        )

    @app.route("/vote/<int:voter_number>", methods=["GET", "POST"])
    def vote(voter_number: int):
        game = get_game()
        if not game:
            return redirect(url_for("index"))

        if voter_number != game["current_vote"]:
            return redirect(
                url_for("vote_pass_screen", voter_number=game["current_vote"])
            )

        current_voter = game["players"][voter_number - 1]
        options = get_options()
        allow_self_vote = options.get("allow_self_vote", False)
        allow_skip_vote = options.get("allow_skip_vote", False)

        if request.method == "POST":
            voted_for_raw = request.form.get("voted_for")

            if allow_skip_vote and voted_for_raw == "skip":
                return redirect(
                    url_for("confirm_vote", voter_number=voter_number, voted_for="skip")
                )

            try:
                voted_for = int(voted_for_raw)
            except (TypeError, ValueError):
                eligible_players = (
                    game["players"]
                    if allow_self_vote
                    else [
                        player
                        for player in game["players"]
                        if player["id"] != current_voter["id"]
                    ]
                )
                return render_template(
                    "vote.html",
                    voter_number=voter_number,
                    voter_name=current_voter["name"],
                    total_players=game["player_count"],
                    players=eligible_players,
                    error="Choose a valid option.",
                    allow_self_vote=allow_self_vote,
                    allow_skip_vote=allow_skip_vote,
                )

            valid_ids = (
                {player["id"] for player in game["players"]}
                if allow_self_vote
                else {
                    player["id"]
                    for player in game["players"]
                    if player["id"] != current_voter["id"]
                }
            )

            if voted_for not in valid_ids:
                eligible_players = (
                    game["players"]
                    if allow_self_vote
                    else [
                        player
                        for player in game["players"]
                        if player["id"] != current_voter["id"]
                    ]
                )
                return render_template(
                    "vote.html",
                    voter_number=voter_number,
                    voter_name=current_voter["name"],
                    total_players=game["player_count"],
                    players=eligible_players,
                    error="You cannot vote for yourself.",
                    allow_self_vote=allow_self_vote,
                    allow_skip_vote=allow_skip_vote,
                )

            return redirect(
                url_for("confirm_vote", voter_number=voter_number, voted_for=voted_for)
            )

        eligible_players = (
            game["players"]
            if allow_self_vote
            else [
                player
                for player in game["players"]
                if player["id"] != current_voter["id"]
            ]
        )

        return render_template(
            "vote.html",
            voter_number=voter_number,
            voter_name=current_voter["name"],
            total_players=game["player_count"],
            players=eligible_players,
            error=None,
            allow_self_vote=allow_self_vote,
            allow_skip_vote=allow_skip_vote,
        )

    @app.route("/confirm_vote/<int:voter_number>/<voted_for>", methods=["GET", "POST"])
    def confirm_vote(voter_number: int, voted_for: str):
        game = get_game()
        if not game:
            return redirect(url_for("index"))

        if voter_number != game["current_vote"]:
            return redirect(
                url_for("vote_pass_screen", voter_number=game["current_vote"])
            )

        current_voter = game["players"][voter_number - 1]
        options = get_options()
        allow_self_vote = options.get("allow_self_vote", False)
        allow_skip_vote = options.get("allow_skip_vote", False)

        if voted_for == "skip":
            if not allow_skip_vote:
                return redirect(url_for("vote", voter_number=voter_number))
            voted_player = None
        else:
            try:
                voted_for_id = int(voted_for)
            except ValueError:
                return redirect(url_for("vote", voter_number=voter_number))

            valid_ids = (
                {player["id"] for player in game["players"]}
                if allow_self_vote
                else {
                    player["id"]
                    for player in game["players"]
                    if player["id"] != current_voter["id"]
                }
            )

            if voted_for_id not in valid_ids:
                return redirect(url_for("vote", voter_number=voter_number))

            voted_player = next(
                player for player in game["players"] if player["id"] == voted_for_id
            )

        if request.method == "POST":
            game["players"][voter_number - 1]["vote"] = (
                "skip" if voted_for == "skip" else int(voted_for)
            )
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
            voted_for=voted_for,
            total_players=game["player_count"],
        )

    @app.route("/count_votes")
    def count_votes():
        game = get_game()
        if not game:
            return redirect(url_for("index"))

        votes = [
            player["vote"] for player in game["players"] if player["vote"] is not None
        ]
        counts = Counter(votes)

        if not counts:
            return redirect(url_for("vote_pass_screen", voter_number=1))

        top_votes = max(counts.values())
        leaders = [
            vote_value for vote_value, count in counts.items() if count == top_votes
        ]

        if len(leaders) > 1:
            options = get_options()
            tie_breaker = options.get("tie_breaker", "impostor_wins")

            if tie_breaker == "revote":
                game["accused_id"] = None
                game["vote_result"] = "tie_revote"
                game["winner"] = None
                game["current_vote"] = 1

                for player in game["players"]:
                    player["vote"] = None

                session["game"] = game
                return redirect(url_for("vote_pass_screen", voter_number=1))

            game["accused_id"] = None
            game["vote_result"] = "tie"
            game["winner"] = "Impostor"
            session["game"] = game
            return redirect(url_for("results"))

        winner_vote = leaders[0]

        if winner_vote == "skip":
            game["accused_id"] = None
            game["vote_result"] = "skipped"
            game["winner"] = "Impostor"
            session["game"] = game
            return redirect(url_for("results"))

        accused_id = winner_vote
        game["accused_id"] = accused_id
        game["vote_result"] = (
            "caught" if accused_id == game["impostor_id"] else "missed"
        )
        session["game"] = game

        if accused_id == game["impostor_id"]:
            options = get_options()

            if options.get("impostor_guess", True):
                return redirect(url_for("guess_word"))

            game["winner"] = "Crewmates"
            session["game"] = game
            return redirect(url_for("results"))

        game["winner"] = "Impostor"
        session["game"] = game
        return redirect(url_for("results"))

    @app.route("/guess", methods=["GET", "POST"])
    def guess_word():
        game = get_game()
        if not game:
            return redirect(url_for("index"))

        options = get_options()
        if not options.get("impostor_guess", True):
            return redirect(url_for("results"))

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
            categories=get_categories(),
            difficulties=get_difficulties(),
            current_category=game["category"],
            current_difficulty=game["difficulty"],
        )

    @app.route("/reset", methods=["POST"])
    def reset():
        session.pop("game", None)
        session.pop("setup", None)
        session.pop("used_words_by_key", None)
        return redirect(url_for("index"))

    @app.route("/options", methods=["GET", "POST"])
    def options():
        if request.method == "POST":
            options = {
                "allow_self_vote": request.form.get("allow_self_vote") == "on",
                "allow_skip_vote": request.form.get("allow_skip_vote") == "on",
                "tie_breaker": request.form.get("tie_breaker", "impostor_wins"),
                "impostor_guess": request.form.get("impostor_guess") == "on",
                "rotate_players": request.form.get("rotate_players") == "on"
            }

            session["options"] = options
            return redirect(url_for("index"))

        return render_template("options.html", options=get_options())
