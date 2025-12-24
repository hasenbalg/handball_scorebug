const socket = io();

function formatTime(sec) {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

socket.on("state_update", (state) => {
    document.getElementById("home_score").textContent = state.home_score;
    document.getElementById("away_score").textContent = state.away_score;

    document.getElementById("home_color").value = state.home_color;
    document.getElementById("away_color").value = state.away_color;

    if (state.running) {
        document.getElementById("running-indicator").innerText = '▶ running';
    } else {
        document.getElementById("running-indicator").innerText = '⏸ Paused';
    }

    document.getElementById("current-time").innerText = state.time;
    document.getElementById("time").dataset.running = state.running;

    // Highlight current period
    document.querySelectorAll(".period-item").forEach((el) => {
        if (parseInt(el.dataset.index) === state.period_index) {
            el.classList.add("active");
        } else {
            el.classList.remove("active");
        }
    });

    // Suspensions
    const homeList = document.getElementById("susp_list_home");
    const awayList = document.getElementById("susp_list_away");
    homeList.innerHTML = "";
    awayList.innerHTML = "";

    // HOME suspensions
    (state.home_suspensions || []).forEach((s, index) => {
        const li = document.createElement("li");
        let text = `#${s.player} – ${formatTime(s.remaining)}`;
        li.textContent = text;

        const btn = document.createElement("button");
        btn.textContent = "Undo";
        btn.onclick = () => {
            sendUpdate({ delete_suspension_home: index });
        };

        li.appendChild(btn);
        homeList.appendChild(li);
    });

    // AWAY suspensions
    (state.away_suspensions || []).forEach((s, index) => {
        const li = document.createElement("li");
        let text = `#${s.player} – ${formatTime(s.remaining)}`;
        li.textContent = text;

        const btn = document.createElement("button");
        btn.textContent = "Undo";
        btn.onclick = () => {
            sendUpdate({ delete_suspension_away: index });
        };

        li.appendChild(btn);
        awayList.appendChild(li);
    });

    // Cards
    const homeCardsList = document.getElementById("cards_list_home");
    const awayCardsList = document.getElementById("cards_list_away");
    homeCardsList.innerHTML = "";
    awayCardsList.innerHTML = "";

    // HOME cards
    (state.home_cards || []).forEach((s, index) => {
        const li = document.createElement("li");
                console.log(s);

        // let text = `#${s.player}– ${s.color.toUpperCase()} – ${formatTime(s.remaining)}`;
        let text = `#${s.player} – ${s.color} – ${formatTime(s.remaining)}`;
        li.textContent = text;

        const btn = document.createElement("button");
        btn.textContent = "Undo";
        btn.onclick = () => {
            sendUpdate({ delete_card_home: index });
        };

        li.appendChild(btn);
        homeCardsList.appendChild(li);
    });


    // AWAY cards
    (state.away_cards || []).forEach((s, index) => {
        const li = document.createElement("li");
        console.log(s);
        
        // let text = `#${s.player} – ${s.color.toUpperCase()} – ${formatTime(s.remaining)}`;
        let text = `#${s.player} – ${s.color} – ${formatTime(s.remaining)}`;
        li.textContent = text;

        const btn = document.createElement("button");
        btn.textContent = "Undo";
        btn.onclick = () => {
            sendUpdate({ delete_card_away: index });
        };

        li.appendChild(btn);
        awayCardsList.appendChild(li);
    });

    // Timeout status
    const homeStatus = document.getElementById("home_timeout_status");
    const awayStatus = document.getElementById("away_timeout_status");

    if (state.home_timeout_active) {
        homeStatus.textContent = `Active – ${formatTime(state.home_timeout_remaining)}`;
    } else {
        homeStatus.textContent = '';
    }

    if (state.away_timeout_active) {
        awayStatus.textContent = `Active – ${formatTime(state.away_timeout_remaining)}`;
    } else {
        awayStatus.textContent = '';
    }
});

function sendUpdate(payload) {
    socket.emit("update", payload);
}

function isGreenish(hex) {
    const r = parseInt(hex.substr(1, 2), 16);
    const g = parseInt(hex.substr(3, 2), 16);
    const b = parseInt(hex.substr(5, 2), 16);

    const rNorm = r / 255;
    const gNorm = g / 255;
    const bNorm = b / 255;

    const max = Math.max(rNorm, gNorm, bNorm);
    const min = Math.min(rNorm, gNorm, bNorm);
    const delta = max - min;

    let h = 0;
    if (delta !== 0) {
        if (max === rNorm) h = ((gNorm - bNorm) / delta) % 6;
        else if (max === gNorm) h = (bNorm - rNorm) / delta + 2;
        else h = (rNorm - gNorm) / delta + 4;
    }
    h = Math.round(h * 60);
    if (h < 0) h += 360;

    if (h >= 70 && h <= 170) return true;
    if (g > r * 1.3 && g > b * 1.3) return true;

    return false;
}

function changeScore(team, delta) {
    const id = team + "_score";
    let value = parseInt(document.getElementById(id).textContent);
    value = Math.max(0, value + delta);
    sendUpdate({ [id]: value });
}

function saveColors() {
    const home = document.getElementById("home_color").value;
    const away = document.getElementById("away_color").value;

    if (isGreenish(home)) {
        alert("Home color is too green for chroma keying. Please choose another color.");
        return;
    }

    if (isGreenish(away)) {
        alert("Away color is too green for chroma keying. Please choose another color.");
        return;
    }

    sendUpdate({
        home_color: home,
        away_color: away
    });
}

function saveState() {
    sendUpdate({
        home_team: document.getElementById("home_team").value,
        away_team: document.getElementById("away_team").value,
        home_score: parseInt(document.getElementById("home_score").textContent),
        away_score: parseInt(document.getElementById("away_score").textContent)
    });
}

function selectPeriod(index) {
    sendUpdate({ set_period_index: index });
}

function applyTimeChange() {
    const value = document.getElementById("time").value;
    sendUpdate({ set_time: value });
    document.getElementById("time").value = '';
}

function addSuspension(team) {
    const id = team + "_susp_player";
    const player = document.getElementById(id).value;
    if (player) {
        // send object with optional card
        const payload = { player };
        sendUpdate({ ["add_suspension_" + team]: payload });
        document.getElementById(id).value = "";
    }
}

function addCard(team, card) {
    const id = team + "_card_player";
    const player = document.getElementById(id).value;
    if (player) {
        // send object with optional card
        const payload = { player };
        if (card) payload.card = card;
        sendUpdate({ ["add_card_" + team]: payload });
        document.getElementById(id).value = "";
    }
}

// Keyboard Shortcuts
document.addEventListener("keydown", (e) => {
    const active = document.activeElement;
    if (active && (active.tagName === "INPUT" || active.tagName === "TEXTAREA")) {
        return;
    }

    const key = e.key.toLowerCase();

    if (key === "h") {
        if (e.shiftKey) changeScore("home", -1);
        else changeScore("home", 1);
    }

    if (key === "a") {
        if (e.shiftKey) changeScore("away", -1);
        else changeScore("away", 1);
    }

    if (e.code === "Space") {
        e.preventDefault();
        const running = document.getElementById("time").dataset.running === "true";
        if (running) sendUpdate({ stop_timer: true });
        else sendUpdate({ start_timer: true });
    }

    if (key === "p") {
        sendUpdate({ next_period: true });
    }

    if (key === "s") {
        saveState();
    }

    if (key === "t") {
        document.getElementById("time").focus();
    }

    if (key === "c") {
        sendUpdate({side_change: true});
    }
});

document.getElementById("time").addEventListener("change", applyTimeChange);
document.getElementById("time").addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        applyTimeChange();
        e.target.blur();
    }
});
