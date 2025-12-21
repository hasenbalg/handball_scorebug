# handball_scorebug

A handball scoreburgbug that can be used with croma keying for a handball live video stream.

![Frontend](<Screenshot 2025-12-14 at 22-38-57 Handball Scoreboard Display.png>)
![Backend](<Screenshot 2025-12-14 at 22-39-44 Handball Scoreboard Control.png>)
---

# Run
```
docker compose up --build

## Requirements

- Python 3.10+
- Redis Server
- pip

---

## Setup (Python Virtual Environment)

Create and activate a virtual environment:

```bash
python3 -m venv env
source env/bin/activate   # Linux / macOS

# On Windows:
# venv\Scripts\activate
```

Install dependencies:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Installing Redis

### Linux 

#### (Debian/Ubuntu)
```bash
sudo apt update
sudo apt install redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server
```

#### (Redhat/Fedora)
```bash
sudo dnf update
sudo dnf install redis
sudo systemctl enable redis
sudo systemctl start redis
```

### macOS (Homebrew)

```bash
brew install redis
brew services start redis
```

### Windows (WSL recommended)

```bash
sudo apt update
sudo apt install redis-server
sudo service redis-server start
```

---

## Running the Project

Start Redis (if not already running):

```bash
redis-server
```

Run the scoreboard:

```bash
python app.py
```

Open the control panel:

```
http://localhost:5000/
```

Open the display:

```
http://localhost:5000/display
```

---

## Features

- Live scoreboard
- Timer with drift‑free updates
- Suspensions
- Team timeouts
- 7‑meter shootout mode
- Redis‑backed persistent state
- WebSocket real‑time updates

---



