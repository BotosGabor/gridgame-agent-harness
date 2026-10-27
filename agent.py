#!/usr/bin/env python3
"""A minimal agent for the grid-game camp. It talks only to the game server,
which plays the game, passes your chats on to the model, and saves every run.

    python3 agent.py --list                       the games and levels you may play now
    python3 agent.py --game <key> --level 0       one run of one level
    python3 agent.py --all                        one run of every level you may play

This file is the protocol and the loop. Your harness (what the model is told,
what it sees, how its reply becomes moves) is harness.py: change that.

Settings come from config.json next to this file, or environment variables:
    SERVER     the game site's address
    AGENT_KEY  your team's agent key: never commit it
    PLAYER     your device (64 hex characters, optional): the runs are shown as yours
    MODEL      an OpenRouter model id (optional: the server's default otherwise)
"""

import argparse
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import harness

HERE = Path(__file__).resolve().parent
CODES = {"UP": "U", "DOWN": "D", "LEFT": "L", "RIGHT": "R", "SPACE": "S", "NOOP": "n"}
BUSY = (429, 502, 503, 504)   # the server is busy for a moment: try again
MAX_STEPS = 5000              # the most steps a run may have


def settings():
    path = HERE / "config.json"
    config = json.loads(path.read_text()) if path.exists() else {}
    found = {k: os.environ.get(k) or config.get(k) or "" for k in ("SERVER", "AGENT_KEY", "PLAYER", "MODEL")}
    missing = [k for k in ("SERVER", "AGENT_KEY") if not found[k]]
    if missing:
        sys.exit(f"Set {' and '.join(missing)} in config.json or the environment (see README.md).")
    found["SERVER"] = found["SERVER"].rstrip("/")
    return found


class Server:
    def __init__(self, config):
        self.config = config

    def call(self, method, path, body=None):
        """The server's JSON answer, retrying while it's busy (1, 2, 4, 8, 16 s)."""
        for attempt in range(6):
            request = urllib.request.Request(
                f"{self.config['SERVER']}/api/{path}", method=method,
                data=None if body is None else json.dumps(body).encode(),
                headers={"X-Agent-Key": self.config["AGENT_KEY"], "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(request, timeout=120) as reply:
                    return json.loads(reply.read())
            except urllib.error.HTTPError as error:
                text = error.read().decode(errors="replace")
                if error.code not in BUSY or attempt == 5:
                    raise RuntimeError(f"{method} /api/{path}: {error.code} {text}") from None
            except urllib.error.URLError as error:
                if attempt == 5:
                    raise RuntimeError(f"{method} /api/{path}: {error.reason}") from None
            time.sleep(2 ** attempt)

    def phase(self):
        """{index, name, evening, tools}: tools empty means the model chats (Day 3)."""
        return self.call("GET", "agent/phase")

    def games(self):
        """{key: {game, name, levels: {"0": map, ...}}}: never the rules."""
        return self.call("GET", "agent/games")

    def play(self, run, game, level, actions, **extra):
        """Replays the run's every step so far: {board, score, time, won, ended}."""
        return self.call("POST", "agent/play", {"run": run, "game": game, "level": level,
                                                "actions": actions, **extra})

    def chat(self, messages, run, **options):
        """The model's reply: {reply, tokens, cost, spent, budget}."""
        body = {"messages": messages, "run": run, **options}
        if self.config["MODEL"]:
            body["model"] = self.config["MODEL"]
        return self.call("POST", "agent/chat", body)


def play_run(server, config, game, level, max_replies):
    """One run of a level: board -> model -> moves, until the game ends or the replies run out."""
    run = f"{game[:40]}-{level}-{secrets.token_hex(3)}"
    first = {"player": config["PLAYER"] or None}
    if config["MODEL"]:
        first["model"] = config["MODEL"]
    actions, history, replies = "", [], 0
    state = server.play(run, game, level, actions, **first)
    print(f"\n=== run {run}: {game} level {level}")
    try:
        while not state["ended"] and replies < max_replies and len(actions) < MAX_STEPS:
            observation = harness.describe(state)
            answer = server.chat(harness.messages(history, observation), run, **harness.CHAT_OPTIONS)
            replies += 1
            moves = harness.moves(answer["reply"])
            history.append((observation, answer["reply"]))
            actions = (actions + ("".join(CODES[m] for m in moves) or "n"))[:MAX_STEPS]
            state = server.play(run, game, level, actions)
            print(f"[{replies}] {' '.join(moves) or 'NOOP'} -> score {state['score']}, time {state['time']}"
                  f"  (spent ${answer.get('spent', 0):.4f} of ${answer.get('budget', 0):.2f})")
    finally:
        if not state["ended"]:
            try:
                server.play(run, game, level, actions, end=True)   # (the run is saved as it is)
            except RuntimeError as error:
                print(f"couldn't end the run: {error}")
    print(f"=== {'WON' if state['won'] else 'lost' if state['ended'] else 'stopped'}: "
          f"score {state['score']}, time {state['time']}, {replies} replies")
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--list", action="store_true", help="list the games and levels you may play now")
    parser.add_argument("--game", help="a game's key (see --list)")
    parser.add_argument("--level", type=int, default=0)
    parser.add_argument("--all", action="store_true", help="play every level you may play, once each")
    parser.add_argument("--runs", type=int, default=1, help="runs per level")
    parser.add_argument("--max-replies", type=int, default=40, help="model replies per run")
    args = parser.parse_args()
    config = settings()
    server = Server(config)
    phase = server.phase()
    print(f"Phase: {phase['name']}")
    if phase.get("tools"):
        sys.exit(f"This phase's model calls tools ({', '.join(phase['tools'])}); this agent only chats.")
    games = server.games()
    if args.list or not (args.game or args.all):
        for key, game in games.items():
            print(f"{key:32s} {game['name']:32s} levels {', '.join(sorted(game['levels'], key=int))}")
        return
    if args.all:
        todo = [(key, int(level)) for key, game in games.items() for level in sorted(game["levels"], key=int)]
    elif args.game not in games:
        sys.exit(f"{args.game} isn't one of the games you may play now (see --list)")
    else:
        todo = [(args.game, args.level)]
    for game, level in todo:
        for _ in range(args.runs):
            try:
                play_run(server, config, game, level, args.max_replies)
            except RuntimeError as error:
                print(f"error: {error}")
                if " 402 " in f" {error} ":
                    sys.exit("The team's AI budget for this phase is spent.")


if __name__ == "__main__":
    main()
