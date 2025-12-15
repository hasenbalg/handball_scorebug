from flask import Flask, render_template
from flask_socketio import SocketIO
from state import ScoreboardState

import logging

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

    # Timer
    if "set_time" in data:
        state.set_time(data["set_time"])
    if data.get("start_timer"):
        state.start_timer()
    if data.get("stop_timer"):
        state.stop_timer()

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
                susp.get("card")  # may be None
            )
        else:
            player = str(susp).strip() or "??"
            state.add_suspension_home(player, None)

    if "add_suspension_away" in data:
        susp = data["add_suspension_away"]
        if isinstance(susp, dict):
            state.add_suspension_away(
                susp.get("player", "??"),
                susp.get("card")
            )
        else:
            player = str(susp).strip() or "??"
            state.add_suspension_away(player, None)

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

    # Timeouts
    if data.get("timeout_home"):
        state.start_timeout_home()
    if data.get("timeout_away"):
        state.start_timeout_away()

    # Reset
    if data.get("reset"):
        state.reset()

    # Hide eg in pause
    if "hide_scorebug" in data:
        state.hide_scorebug = bool(data["hide_scorebug"])

    # 7m shootout
    if data.get("shootout_start"):
        state.start_shootout()

    if data.get("shootout_stop"):
        state.stop_shootout()

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
            state.save()
            broadcast_state(state)
        except Exception as e:
            log.error("Timer thread error: %s", e)

        socketio.sleep(1)


if __name__ == "__main__":
    log.info("Starting timer thread…")
    socketio.start_background_task(timer_thread)
    socketio.run(app, debug=True, use_reloader=False)
