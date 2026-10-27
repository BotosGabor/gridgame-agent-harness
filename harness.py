"""Your harness: what the model is told, what it sees each turn, and how its
reply becomes moves. agent.py uses the four names below; change everything
else freely (memory, notes, a map of what you've learned, several models...).

Moves are UP DOWN LEFT RIGHT SPACE NOOP. Each takes 4 game ticks (the move,
then 3 of waiting), and the game is paused while the model thinks.
"""

import re

SYSTEM_PROMPT = """You play an unknown grid video game as its avatar, which is probably the A. Nobody tells you the rules: find out what the characters are and how to win by trying, and remember what you learn. Row 0 is the top row; UP moves one row up. Each of your moves takes 4 game ticks (the move, then 3 ticks of waiting; NOOP waits all 4), so everything else in the game moves on meanwhile. Each turn you see the board, the score and the time (in ticks).

Reply in exactly two lines:
THINK: one short sentence: what you notice, why you move, and where you are going.
MOVES: up to 10 moves to make next, separated by spaces, from: UP DOWN LEFT RIGHT SPACE NOOP."""

# Sent with every chat. max_tokens: 1 to 8000; reasoning: minimal, low, medium or high.
# A chat must be answered within about 30 seconds, so keep both modest.
CHAT_OPTIONS = {"max_tokens": 2000, "reasoning": "low"}

KEEP_TURNS = 6   # the earlier turns the model sees again
MAX_MOVES = 10   # the most moves taken from one reply
MOVES = ("UP", "DOWN", "LEFT", "RIGHT", "SPACE", "NOOP")


def describe(state):
    """What the model sees of the game: state is {board, score, time, won, ended}."""
    return f"Score {state['score']}, time {state['time']}.\n{state['board']}"


def messages(history, observation):
    """The chat for this turn: history is [(what the model saw, its reply), ...]."""
    out = [{"role": "system", "content": SYSTEM_PROMPT}]
    for seen, reply in history[-KEEP_TURNS:]:
        out += [{"role": "user", "content": seen}, {"role": "assistant", "content": reply}]
    return out + [{"role": "user", "content": observation}]


def moves(reply):
    """The moves in the model's reply: its MOVES line (else any move words), at most MAX_MOVES."""
    line = next((l for l in reply.splitlines() if l.strip().upper().startswith("MOVES")), reply)
    return [w for w in re.findall(r"[A-Z]+", line.upper()) if w in MOVES][:MAX_MOVES]
