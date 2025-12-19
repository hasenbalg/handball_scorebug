const socket = io();

function formatTime(sec) {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

socket.on("state_update", (state) => {

    // Hide / Show Scorebug
    const scorebug = document.getElementById("scorebug");
    if (state.hide_scorebug) {
        scorebug.classList.add("hidden");
    } else {
        scorebug.classList.remove("hidden");
    }

    // Basic fields
    document.getElementById("home_team").textContent = state.home_team;
    document.getElementById("away_team").textContent = state.away_team;
    document.getElementById("home_score").textContent = state.home_score;
    document.getElementById("away_score").textContent = state.away_score;
    document.getElementById("period").textContent = state.period_name;
    document.getElementById("time").textContent = state.time;

    // Team colors
    const homeBlock = document.querySelector(".team-block.home");
    const awayBlock = document.querySelector(".team-block.away");

    function makeGradient(color) {
        return `linear-gradient(135deg, ${color}, ${color}CC)`;
    }

    homeBlock.style.background = makeGradient(state.home_color);
    awayBlock.style.background = makeGradient(state.away_color);

    // Suspensions
    const hb = document.getElementById("home_badges");
    const ab = document.getElementById("away_badges");
    hb.innerHTML = "";
    ab.innerHTML = "";

    (state.home_suspensions || []).forEach(s => {
        const div = document.createElement("div");
        div.className = "penalty-badge";
        let text = `#${s.player} ${formatTime(s.remaining)}`;

        div.textContent = text;
        hb.appendChild(div);
    });

    (state.away_suspensions || []).forEach(s => {
        const div = document.createElement("div");
        div.className = "penalty-badge";
        let text = `#${s.player} ${formatTime(s.remaining)}`;
        div.textContent = text;
        ab.appendChild(div);
    });

    // Cards
    (state.home_cards || []).forEach(s => {
        const div = document.createElement("div");
        div.className = "card-badge";
        div.classList.add(s.color.toLowerCase()); // add CSS class for card color
        div.textContent = `#${s.player}`;
        hb.appendChild(div);
    });

    (state.away_cards || []).forEach(s => {

        const div = document.createElement("div");
        div.className = "card-badge";
        div.classList.add(s.color.toLowerCase());
        div.textContent = `#${s.player}}`;;
        ab.appendChild(div);
    });

    // TIMEOUTS
    const homeTO = document.getElementById("home_timeout");
    const awayTO = document.getElementById("away_timeout");

    if (state.home_timeout_active) {
        homeTO.textContent = `TIMEOUT ${formatTime(state.home_timeout_remaining)}`;
        homeTO.style.display = "block";
    } else {
        homeTO.style.display = "none";
    }

    if (state.away_timeout_active) {
        awayTO.textContent = `TIMEOUT ${formatTime(state.away_timeout_remaining)}`;
        awayTO.style.display = "block";
    } else {
        awayTO.style.display = "none";
    }

    // SHOOTOUT
    const homeLane = document.getElementById("shootout_home");
    const awayLane = document.getElementById("shootout_away");

    if (state.shootout_active) {
        homeLane.style.display = "flex";
        awayLane.style.display = "flex";

        homeLane.innerHTML = "";
        state.home_shootout.forEach(result => {
            const dot = document.createElement("div");
            dot.className = result ? "so-goal" : "so-miss";
            homeLane.appendChild(dot);
        });

        awayLane.innerHTML = "";
        state.away_shootout.forEach(result => {
            const dot = document.createElement("div");
            dot.className = result ? "so-goal" : "so-miss";
            awayLane.appendChild(dot);
        });

    } else {
        homeLane.style.display = "none";
        awayLane.style.display = "none";
    }
});