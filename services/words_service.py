from pathlib import Path
from flask import session
import json
import random

WORDS_PATH = Path(__file__).resolve().parent.parent / "words.json"

with open(WORDS_PATH, "r", encoding="utf-8") as f:
    WORDS = json.load(f)


def get_categories() -> list[str]:
    return list(WORDS.keys())


def get_difficulties() -> list[str]:
    return ["easy", "hard"]


def get_words_for(category: str, difficulty: str) -> list[str]:
    return WORDS[category][difficulty]


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
