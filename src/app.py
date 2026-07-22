"""
High School Management System API

A simple FastAPI application that uses SQLite persistence for activities
and member signups.
"""

import sqlite3
from pathlib import Path
from typing import Dict

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="Mergington High School API",
    description="API for viewing and signing up for extracurricular activities",
)

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=current_dir / "static"), name="static")

DB_PATH = current_dir / "activities.db"

INITIAL_ACTIVITIES = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"],
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"],
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"],
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"],
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"],
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"],
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"],
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"],
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"],
    },
}


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def setup_database() -> None:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS activities (
            name TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            schedule TEXT NOT NULL,
            max_participants INTEGER NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS participants (
            activity_name TEXT NOT NULL,
            email TEXT NOT NULL,
            PRIMARY KEY (activity_name, email),
            FOREIGN KEY (activity_name) REFERENCES activities(name) ON DELETE CASCADE
        )
        """
    )
    connection.commit()

    cursor.execute("SELECT COUNT(*) AS count FROM activities")
    if cursor.fetchone()[0] == 0:
        for name, data in INITIAL_ACTIVITIES.items():
            cursor.execute(
                "INSERT INTO activities(name, description, schedule, max_participants) VALUES (?, ?, ?, ?)",
                (name, data["description"], data["schedule"], data["max_participants"]),
            )
            for email in data["participants"]:
                cursor.execute(
                    "INSERT INTO participants(activity_name, email) VALUES (?, ?)",
                    (name, email),
                )
        connection.commit()

    connection.close()


def fetch_activity(activity_name: str) -> Dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM activities WHERE name = ?", (activity_name,))
    row = cursor.fetchone()
    if row is None:
        connection.close()
        return None

    cursor.execute(
        "SELECT email FROM participants WHERE activity_name = ? ORDER BY email",
        (activity_name,),
    )
    participants = [participant["email"] for participant in cursor.fetchall()]
    connection.close()

    return {
        "description": row["description"],
        "schedule": row["schedule"],
        "max_participants": row["max_participants"],
        "participants": participants,
    }


def fetch_all_activities() -> Dict[str, object]:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM activities ORDER BY name")
    rows = cursor.fetchall()

    activities: Dict[str, object] = {}
    for row in rows:
        activity_name = row["name"]
        cursor.execute(
            "SELECT email FROM participants WHERE activity_name = ? ORDER BY email",
            (activity_name,),
        )
        participants = [participant["email"] for participant in cursor.fetchall()]
        activities[activity_name] = {
            "description": row["description"],
            "schedule": row["schedule"],
            "max_participants": row["max_participants"],
            "participants": participants,
        }

    connection.close()
    return activities


@app.on_event("startup")
def on_startup() -> None:
    setup_database()


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities() -> Dict[str, object]:
    return fetch_all_activities()


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str = Query(...)) -> Dict[str, str]:
    activity = fetch_activity(activity_name)
    if activity is None:
        raise HTTPException(status_code=404, detail="Activity not found")

    if email in activity["participants"]:
        raise HTTPException(status_code=400, detail="Student is already signed up")

    if len(activity["participants"]) >= activity["max_participants"]:
        raise HTTPException(status_code=400, detail="Activity is full")

    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "INSERT INTO participants(activity_name, email) VALUES (?, ?)",
            (activity_name, email),
        )
        connection.commit()
    except sqlite3.IntegrityError:
        connection.close()
        raise HTTPException(status_code=400, detail="Student is already signed up")

    connection.close()
    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str = Query(...)) -> Dict[str, str]:
    activity = fetch_activity(activity_name)
    if activity is None:
        raise HTTPException(status_code=404, detail="Activity not found")

    if email not in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is not signed up for this activity",
        )

    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "DELETE FROM participants WHERE activity_name = ? AND email = ?",
        (activity_name, email),
    )
    connection.commit()
    connection.close()

    return {"message": f"Unregistered {email} from {activity_name}"}


if __name__ == "__main__":
    import uvicorn

    setup_database()
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
