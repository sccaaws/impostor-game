from flask import session


def get_default_options():
    return {
        "allow_self_vote": False,
        "allow_skip_vote": False,
        "tie_breaker": "impostor_wins",
        "impostor_guess": True,
    }


def get_options():
    return session.get("options", get_default_options())
