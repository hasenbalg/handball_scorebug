const socket = io();

function formatTime(sec) {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

// Utility: convert hex color to RGB
function hexToRgb(hex) {
    hex = hex.replace(/^#/, "");
    if (hex.length === 3) {
        hex = hex.split("").map(c => c + c).join("");
    }
    const num = parseInt(hex, 16);
    return {
        r: (num >> 16) & 255,
        g: (num >> 8) & 255,
        b: num & 255
    };
}

// Utility: calculate relative luminance
function getLuminance({ r, g, b }) {
    const a = [r, g, b].map(v => {
        v /= 255;
        return v <= 0.03928
            ? v / 12.92
            : Math.pow((v + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * a[0] + 0.7152 * a[1] + 0.0722 * a[2];
}

// Decide text color based on background
function getTextColor(bgHex) {
    const rgb = hexToRgb(bgHex);
    const lum = getLuminance(rgb);
    return lum > 0.5 ? "#000" : "#fff"; // light background → black text
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

    // Adjust text color for team names and scores
    const homeTextColor = getTextColor(state.home_color);
    const awayTextColor = getTextColor(state.away_color);

    document.getElementById("home_team").style.color = homeTextColor;
    document.getElementById("home_score").style.color = homeTextColor;

    document.getElementById("away_team").style.color = awayTextColor;
    document.getElementById("away_score").style.color = awayTextColor;

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
        div.textContent = `#${s.player}`;;
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