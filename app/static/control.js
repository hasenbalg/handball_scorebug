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
        const dqH = (state.home_disqualified || []).includes(s.player);
        let text = `#${s.player} – ${formatTime(s.remaining)} (×${(state.home_suspension_counts || {})[s.player] || 1})${dqH ? " DQ" : ""}`;
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
        const dqA = (state.away_disqualified || []).includes(s.player);
        let text = `#${s.player} – ${formatTime(s.remaining)} (×${(state.away_suspension_counts || {})[s.player] || 1})${dqA ? " DQ" : ""}`;
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

    // Technical timeout status (#6)
    const techStatus = document.getElementById("technical_timeout_status");
    if (techStatus) {
        techStatus.textContent = state.technical_timeout_active
            ? `Active – ${formatTime(state.technical_timeout_remaining)}`
            : '';
    }

    // Team time-out quota (#1): 3 per match, 2 per half, none in OT
    for (const side of ["home", "away"]) {
        const el = document.getElementById(side + "_timeout_status");
        if (!el || !state[side + "_timeouts"]) continue;
        const q = state[side + "_timeouts"];
        let text = el.textContent.replace(/\s*\| *TO \d\/\d.*$/, "");
        if (q.total) {
            text += ` | TO ${q.total}/${q.max}`;
            if (q.over_total) text += " ⚠ over quota";
            else if (q.over_half) text += " ⚠ 2 per half max";
            if (q.ot_used) text += " ⚠ no TO in OT";
        }
        el.textContent = text;
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
    if (delta > 0) {
        // Goal: server-side increment + optional scorer (#4)
        const input = document.getElementById(team + "_scorer");
        const scorer = input ? input.value.trim() : "";
        sendUpdate({ [team + "_score_change"]: 1, [team + "_scorer"]: scorer || null });
    } else {
        // Correction: remove last goal (and its scorer)
        sendUpdate({ [team + "_score_change"]: -1 });
    }
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

// -----------------------------
// 7m shootout protocol status (#15)
// -----------------------------
function startShootout() {
    const t = document.getElementById("shootout_start_team").value;
    sendUpdate({ shootout_start: { starting_team: t } });
}

function renderShootoutStatus(state) {
    const box = document.getElementById("shootout_status");
    if (!box) return;
    const label = t => (t === "home" ? state.home_team : state.away_team);

    let html = "";
    if (state.shootout_active) {
        if (state.shootout_confirmed_winner) {
            html = `🏆 ${label(state.shootout_confirmed_winner)} wins — input locked ` +
                `<button onclick="sendUpdate({ shootout_unconfirm: true })">Un-confirm</button>`;
        } else if (state.shootout_suggested_winner) {
            const w = state.shootout_suggested_winner;
            html = `Rules force a win for <b>${label(w)}</b>. ` +
                `<button onclick="sendUpdate({ shootout_confirm: { team: '${w}' } })">Confirm winner</button>`;
        } else {
            html = `Next throw: <b>${label(state.shootout_next_team)}</b>`;
        }
    }
    box.innerHTML = html;

    // Confirmed result: disable attempt/undo input until un-confirm
    document.querySelectorAll(".so-input").forEach(
        b => { b.disabled = !!state.shootout_confirmed_winner; });
}

socket.on("state_update", renderShootoutStatus);

// -----------------------------
// Match log / event timeline (#5)
// -----------------------------
function logEntryLabel(e) {
    switch (e.type) {
        case "goal": return "GOAL";
        case "suspension": return "2min";
        case "disqualification": return "DQ";
        case "card": return e.detail === "red" ? "RED" : "YELLOW";
        case "timeout": return "TIMEOUT";
        case "technical_timeout": return "TECH TIMEOUT";
        case "period": return "→ " + (e.detail || "");
        case "7m": return e.detail === "goal" ? "7m GOAL" : "7m MISS";
        default: return e.type.toUpperCase();
    }
}

function renderMatchLog(state) {
    const el = document.getElementById("match_log");
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 30;
    el.innerHTML = (state.match_log || []).map(e => {
        const sideClass = e.side || "neutral";
        const sideText = e.side ? e.side.toUpperCase() : "";
        const player = e.player ? ` #${e.player}` : "";
        return `<div class="entry">` +
            `<span class="clock">${e.clock}</span> ` +
            `<span class="period">${e.period}</span> ` +
            `<span class="${sideClass}">${sideText}${player} ${logEntryLabel(e)}</span>` +
            `</div>`;
    }).join("");
    if (atBottom) el.scrollTop = el.scrollHeight;
}

socket.on("state_update", renderMatchLog);

// -----------------------------
// Referee whistle / clock rules (#11)
// -----------------------------
document.addEventListener("keydown", (e) => {
    const active = document.activeElement;
    if (active && (active.tagName === "INPUT" || active.tagName === "TEXTAREA")) {
        return;
    }
    if (e.key.toLowerCase() === "w") {
        e.preventDefault();
        sendUpdate({ referee_whistle: true });
    }
});

function renderClockRulesStatus(state) {
    const cb = document.getElementById("auto_stop_susp");
    if (cb && document.activeElement !== cb) {
        cb.checked = !!state.auto_stop_on_suspension;
    }
    const hint = document.getElementById("clock-hint");
    if (hint) {
        hint.textContent =
            (state.at_period_cap && !state.running)
                ? "Clock at end of period. If this was a premature signal, keep the teams on court and play the remaining time (2:7)."
                : "";
    }
}
socket.on("state_update", renderClockRulesStatus);

// -----------------------------
// Match configuration (#10)
// -----------------------------
let _lastPeriodNames = null;

function renderMatchConfig(state) {
    // Period list follows the configuration (halves length + overtime)
    const names = state.period_names || [];
    if (JSON.stringify(names) !== JSON.stringify(_lastPeriodNames)) {
        _lastPeriodNames = names;
        const list = document.getElementById("period_list");
        list.innerHTML = "";
        names.forEach((name, i) => {
            const el = document.createElement("div");
            el.className = "period-item";
            el.dataset.index = i;
            el.textContent = name;
            el.onclick = () => selectPeriod(i);
            if (i === state.period_index) el.classList.add("active");
            list.appendChild(el);
        });
    } else {
        document.querySelectorAll(".period-item").forEach((el) => {
            el.classList.toggle("active", parseInt(el.dataset.index) === state.period_index);
        });
    }

    // Config controls (skip focused element to keep the picker usable)
    const setVal = (id, v) => {
        const el = document.getElementById(id);
        if (el && document.activeElement !== el) el.value = v;
    };
    setVal("cfg_match_type", state.match_type);
    setVal("cfg_half_minutes", String(state.half_minutes));
    const ot = document.getElementById("cfg_overtime");
    if (ot && document.activeElement !== ot) ot.checked = !!state.overtime_enabled;
}
socket.on("state_update", renderMatchConfig);
