from flask import Flask, render_template
from flask_socketio import SocketIO
from state import ScoreboardState

import logging
logging.getLogger("geventwebsocket.handler").setLevel(logging.WARNING)
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger("timer")

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")


def broadcast_state(state=None):
    if state is None:
        state = ScoreboardState.load()

    public = state.to_public_dict()
    socketio.emit("state_update", public)


@app.route("/")
def control():
    state = ScoreboardState.load()
    return render_template("control.html", game_state=state.to_public_dict())


@app.route("/display")
def display():
    state = ScoreboardState.load()
    return render_template("display.html", game_state=state.to_public_dict())


@app.route("/cube")
def cube():
    state = ScoreboardState.load()
    return render_template("cube.html", game_state=state.to_public_dict())


@socketio.on("update")
def handle_update(data):
    state = ScoreboardState.load()

    # Team names
    if "home_team" in data:
        state.home_team = data["home_team"]
    if "away_team" in data:
        state.away_team = data["away_team"]

    # Colors
    if "home_color" in data:
        state.home_color = data["home_color"]
    if "away_color" in data:
        state.away_color = data["away_color"]

    # Scores
    if "home_score" in data:
        state.home_score = int(data["home_score"])
    if "away_score" in data:
        state.away_score = int(data["away_score"])
    # Score (+/- are goals with optional scorer #4; absolute set via
    # "Save / Push" is a correction and deliberately not logged)
    for side in ("home", "away"):
        change = int(data.get(f"{side}_score_change", 0) or 0)
        if change > 0:
            scorer = data.get(f"{side}_scorer")
            for _ in range(change):
                state.goal(side, scorer)
        elif change < 0:
            for _ in range(-change):
                state.undo_goal(side)

    # Timer
    if "set_time" in data:
        state.set_time(data["set_time"])
    if data.get("start_timer"):
        state.start_timer()
    if data.get("stop_timer"):
        state.stop_timer()
    if data.get("referee_whistle"):
        state.referee_whistle()
    if "auto_stop_on_suspension" in data:
        state.auto_stop_on_suspension = bool(data["auto_stop_on_suspension"])
    if "match_config" in data:
        cfg = data["match_config"] or {}
        state.set_match_configuration(
            match_type=cfg.get("match_type"),
            half_minutes=cfg.get("half_minutes"),
            overtime_enabled=cfg.get("overtime_enabled"),
        )
        # config may shrink the period list; keep the index valid
        state.set_period_index(state.period_index)

    # Period
    if data.get("next_period"):
        state.next_period()
    if "set_period_index" in data:
        try:
            idx = int(data["set_period_index"])
            state.set_period_index(idx)
        except ValueError:
            pass

    # Suspensions
    if "add_suspension_home" in data:
        susp = data["add_suspension_home"]
        if isinstance(susp, dict):
            state.add_suspension_home(
                susp.get("player", "??"),
            )
        else:
            player = str(susp).strip() or "??"
            state.add_suspension_home(player)

    if "add_suspension_away" in data:
        susp = data["add_suspension_away"]
        if isinstance(susp, dict):
            state.add_suspension_away(
                susp.get("player", "??"),
            )
        else:
            player = str(susp).strip() or "??"
            state.add_suspension_away(player)

    if "delete_suspension_home" in data:
        try:
            state.delete_suspension_home(int(data["delete_suspension_home"]))
        except Exception:
            pass

    if "delete_suspension_away" in data:
        try:
            state.delete_suspension_away(int(data["delete_suspension_away"]))
        except Exception:
            pass

   # Cards
    if "add_card_home" in data:
        card = data["add_card_home"]
        if isinstance(card, dict):
            state.add_card_home(
                card.get("player", "??"),
                card.get("card")  # may be None
            )
        else:
            player = str(card).strip() or "??"
            state.add_card_home(player, None)

    if "add_card_away" in data:
        card = data["add_card_away"]
        if isinstance(card, dict):
            state.add_card_away(
                card.get("player", "??"),
                card.get("card")
            )
        else:
            player = str(card).strip() or "??"
            state.add_card_away(player, None)

    if "delete_card_home" in data:
        try:
            state.delete_card_home(int(data["delete_card_home"]))
        except Exception:
            pass

    if "delete_card_away" in data:
        try:
            state.delete_card_away(int(data["delete_card_away"]))
        except Exception:
            pass

    # Timeouts
    if data.get("timeout_home"):
        state.start_timeout_home()
    if data.get("timeout_away"):
        state.start_timeout_away()
    if data.get("technical_timeout"):
        state.start_technical_timeout()

    # Reset
    if data.get("reset"):
        state.reset()

    # Hide eg in pause
    if "hide_scorebug" in data:
        state.hide_scorebug = bool(data["hide_scorebug"])

    # Match log maintenance (#5)
    if data.get("log_delete_last"):
        state.log_delete_last()

    if data.get("skip_break"):
        state.skip_break()

    # Passive play (#3)
    if data.get("passive_home"):
        state.set_passive("home")
    if data.get("passive_away"):
        state.set_passive("away")
    if data.get("passive_pass"):
        state.passive_pass()
    if data.get("passive_clear"):
        state.set_passive(None)

    # 7m shootout
    if data.get("shootout_start"):
        st = data["shootout_start"]
        starting = st.get("starting_team", "home") if isinstance(st, dict) else "home"
        state.start_shootout(starting)

    if data.get("shootout_stop"):
        state.stop_shootout()

    if data.get("shootout_confirm"):
        st = data["shootout_confirm"]
        team = st.get("team") if isinstance(st, dict) else None
        state.confirm_shootout_winner(team)

    if data.get("shootout_unconfirm"):
        state.unconfirm_shootout_winner()

    if "shootout_home_goal" in data:
        state.add_shootout_attempt(True, True)

    if "shootout_home_miss" in data:
        state.add_shootout_attempt(True, False)

    if "shootout_away_goal" in data:
        state.add_shootout_attempt(False, True)

    if "shootout_away_miss" in data:
        state.add_shootout_attempt(False, False)

    if "shootout_undo_home" in data:
        state.undo_shootout(True)

    if "shootout_undo_away" in data:
        state.undo_shootout(False)

    if "side_change" in data:
        state.side_change()

    state.save()
    broadcast_state(state)


def timer_thread():
    log.info("Timer thread started")
    while True:
        try:
            state = ScoreboardState.load()
            state.update_time()
            state.update_timeouts()
            state.cleanup_suspensions()
            state.cleanup_cards()
            state.save()
            broadcast_state(state)
        except Exception as e:
            log.error("Timer thread error: %s", e)

        socketio.sleep(1)


@socketio.on("connect")
def start_background_tasks():
    global _timer_started
    if not getattr(start_background_tasks, "_started", False):
        socketio.start_background_task(timer_thread)
        start_background_tasks._started = True


# if __name__ == "__main__":
#     log.info("Starting timer thread…")
#     backgroundTask = socketio.start_background_task(timer_thread)
#     socketio.run(app, async_mode="gevent", message_queue="redis://redis:6379/0", debug=True, use_reloader=False, host="0.0.0.0")
