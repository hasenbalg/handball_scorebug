const socket = io();

// -----------------------------
// TIME FORMAT
// -----------------------------
const formatTime = sec =>
    `${String(Math.floor(sec / 60)).padStart(2, "0")}:${String(sec % 60).padStart(2, "0")}`;

// -----------------------------
// COLOR UTILITIES
// -----------------------------
function hexToRgb(hex) {
    hex = hex.replace(/^#/, "");
    if (hex.length === 3) hex = hex.split("").map(c => c + c).join("");

    const num = parseInt(hex, 16);
    return {
        r: (num >> 16) & 255,
        g: (num >> 8) & 255,
        b: num & 255
    };
}

function getLuminance({ r, g, b }) {
    const a = [r, g, b].map(v => {
        v /= 255;
        return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * a[0] + 0.7152 * a[1] + 0.0722 * a[2];
}

const getTextColor = hex => (getLuminance(hexToRgb(hex)) > 0.5 ? "#000" : "#fff");

// -----------------------------
// SOUND ACTIVATION
// -----------------------------
const buzzer = document.getElementById("buzzer");
const activateBtn = document.getElementById("activate_sound");

let soundEnabled = false;

activateBtn?.addEventListener("click", activateSoundOnce, { once: true });
document.addEventListener("click", activateSoundOnce, { once: true });
document.addEventListener("keydown", activateSoundOnce, { once: true });
document.addEventListener("touchstart", activateSoundOnce, { once: true });
document.addEventListener("scroll", activateSoundOnce, { once: true });

function activateSoundOnce() {
    buzzer.volume = 0.01;
    buzzer.play().then(() => {
        buzzer.pause();
        buzzer.currentTime = 0;
        buzzer.volume = 1.0;
        soundEnabled = true;
        activateBtn?.classList.add("hidden");
        console.log("Sound activated");
    }).catch(err => console.warn("Sound activation failed:", err));
}

// -----------------------------
// GOAL ANIMATION
// -----------------------------
let lastHomeScore = null;
let lastAwayScore = null;

function triggerGoalAnimation() {
    const el = document.createElement("div");
    el.className = "goal-anim";
    el.textContent = "GOAL!";
    document.body.appendChild(el);

    const animations = ["play", "side", "zoom"];
    el.classList.add(animations[Math.floor(Math.random() * animations.length)]);

    void el.offsetWidth; // restart animation
    setTimeout(() => el.remove(), 2500);
}

function checkGoalAnimation(state) {
    if (state.running) {
        if (lastHomeScore !== null && state.home_score > lastHomeScore) triggerGoalAnimation();
        if (lastAwayScore !== null && state.away_score > lastAwayScore) triggerGoalAnimation();
    }

    lastHomeScore = state.home_score;
    lastAwayScore = state.away_score;
}

// -----------------------------
// HELPERS
// -----------------------------
const setText = (id, value) => (document.getElementById(id).textContent = value);

function renderBadges(container, suspensions, cards) {
    container.innerHTML = "";

    suspensions?.forEach(s => {
        const div = document.createElement("div");
        div.className = "penalty-badge";
        div.textContent = `#${s.player} ${formatTime(s.remaining)}`;
        container.appendChild(div);
    });

    cards?.forEach(c => {
        const div = document.createElement("div");
        div.className = `card-badge ${c.color.toLowerCase()}`;
        div.textContent = `#${c.player}`;
        container.appendChild(div);
    });
}

function renderTimeout(el, active, remaining) {
    if (active) {
        el.textContent = `TIMEOUT ${formatTime(remaining)}`;
        el.style.display = "block";
    } else {
        el.style.display = "none";
    }
}

function renderShootout(lane, results) {
    lane.innerHTML = "";
    results.forEach(r => {
        const dot = document.createElement("div");
        dot.className = r ? "so-goal" : "so-miss";
        lane.appendChild(dot);
    });
}

// -----------------------------
// BUZZER EVENT
// -----------------------------
socket.on("time_over", () => {
    if (!soundEnabled) return;
    buzzer.currentTime = 0;
    buzzer.play().catch(err => console.warn("Autoplay blocked:", err));
});

// -----------------------------
// MAIN STATE UPDATE
// -----------------------------
socket.on("state_update", (state) => {
    checkGoalAnimation(state);

    document.getElementById("scorebug")
        .classList.toggle("hidden", state.hide_scorebug);

    // Basic fields
    setText("home_team", state.home_team);
    setText("away_team", state.away_team);
    setText("home_score", state.home_score);
    setText("away_score", state.away_score);
    setText("period", state.period_name);
    setText("time", state.time);

    // Colors
    const homeBlock = document.querySelector(".team-block.home");
    const awayBlock = document.querySelector(".team-block.away");

    const makeGradient = c => `linear-gradient(135deg, ${c}, ${c}CC)`;

    homeBlock.style.background = makeGradient(state.home_color);
    awayBlock.style.background = makeGradient(state.away_color);

    const homeColor = getTextColor(state.home_color);
    const awayColor = getTextColor(state.away_color);

    document.getElementById("home_team").style.color = homeColor;
    document.getElementById("home_score").style.color = homeColor;
    document.getElementById("away_team").style.color = awayColor;
    document.getElementById("away_score").style.color = awayColor;

    // Badges
    renderBadges(
        document.getElementById("home_badges"),
        state.home_suspensions,
        state.home_cards
    );
    renderBadges(
        document.getElementById("away_badges"),
        state.away_suspensions,
        state.away_cards
    );

    // Timeouts
    renderTimeout(
        document.getElementById("home_timeout"),
        state.home_timeout_active,
        state.home_timeout_remaining
    );
    renderTimeout(
        document.getElementById("away_timeout"),
        state.away_timeout_active,
        state.away_timeout_remaining
    );

    // Shootout
    const homeLane = document.getElementById("shootout_home");
    const awayLane = document.getElementById("shootout_away");

    if (state.shootout_active) {
        homeLane.style.display = "flex";
        awayLane.style.display = "flex";
        renderShootout(homeLane, state.home_shootout);
        renderShootout(awayLane, state.away_shootout);
    } else {
        homeLane.style.display = "none";
        awayLane.style.display = "none";
    }
});