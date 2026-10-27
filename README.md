# Grid-game agent harness

A minimal agent for the camp's grid games. Fork it, make `harness.py` smarter, and let it play.

- **`agent.py`**: the protocol and the loop. You don't need to change it.
- **`harness.py`**: your harness, meaning what the model is told, what it sees each turn, and how its reply becomes moves. Change this.

It uses only Python's standard library (Python 3.8+), so there's nothing to install.

## Setup

1. **Fork** this repo, then clone your fork.
2. Copy `config.example.json` to `config.json` and fill it in. The values are at the top of `starter_agent.py` in your team's zip:

   | config.json | starter_agent.py |
   |---|---|
   | `SERVER` | `DEFAULT_SERVER` |
   | `AGENT_KEY` | `DEFAULT_KEY` |
   | `PLAYER` | `DEFAULT_PLAYER` (optional: the runs are shown as yours) |
   | `MODEL` | optional: any OpenRouter model id, or leave it empty for the server's default |

> **Never commit `config.json` or your agent key.** Forks of a public repo are public. `config.json` is in `.gitignore`, so keep the key there. You can also use environment variables (`SERVER`, `AGENT_KEY`, `PLAYER`, `MODEL`) instead.

## Run

```bash
python3 agent.py --list                     # the games and levels you may play now
python3 agent.py --game <key> --level 0     # one run of one level
python3 agent.py --all                      # one run of every level you may play
python3 agent.py --all --runs 3             # three runs of each
```

## How a turn works

The agent talks **only to the game server**. The server plays the game, passes your chat to the model, charges your team's budget and saves everything.

1. `POST /api/agent/play` with **every step of the run so far** (one letter per step: `n` wait, `U D L R` move, `S` space). The server replays the level from the start and answers `{board, score, time, won, ended}`.
2. `harness.describe(state)` turns that into text for the model.
3. `harness.messages(history, observation)` builds the chat. `POST /api/agent/chat` sends it to the model and answers `{reply, tokens, cost, spent, budget}`.
4. `harness.moves(reply)` picks the moves out of the reply. They're added to the run's steps, and the loop goes back to 1.

One move takes 4 game ticks (the move, then 3 of waiting). The game is paused while the model thinks.

## Rules

- **No rules, no code.** The model never gets a game's rules. A chat containing game code (VGDL) is refused (403). Learn by playing.
- **Every run is saved** on the server, finished or not. That's what the evening shows.
- **Budget:** each team has an AI budget per phase. Once it's spent, chats are refused (402).
- **At most 2 agents per team at once** (a third gets 409).
- **Keep replies quick:** a chat must be answered in about 30 seconds. Big `max_tokens` or `"reasoning": "high"` can make it fail.

## Ideas for your harness

- Keep notes: let the model write down what it has learned (which character is a key, what kills you) and send them again every turn.
- Describe the board better: coordinates, the avatar's position, what changed since the last turn.
- Ask for fewer moves near danger and more in open space.
- Remember what worked on earlier runs of the same level.
