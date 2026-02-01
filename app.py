from flask import Flask, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
import json
from backend import database

# ================== APP SETUP ==================

app = Flask(__name__)
CORS(app)

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="eventlet"
)

DATA_FILE = "data.json"

# ================== RUNTIME STORAGE ==================

users = {}              # {username: {avatar, sid}}
active_sockets = {}     # {sid: username}
groups = {}             # {group_name: {members, history, avatar}}
private_messages = {}   # {(u1,u2): [messages]}

# ================== DATA LOAD / SAVE ==================

def load_data():
    if not os.path.exists(DATA_FILE):
        return

    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)

        # --- USERS (migrate to DB) ---
        for u, info in data.get("users", {}).items():
            if not database.get_user(u):
                database.add_user(u, info.get("avatar", "👤"))

        for u in database.get_all_users():
            users[u["username"]] = {"avatar": u["avatar"], "sid": None}

        # --- GROUPS ---
        for g, info in data.get("groups", {}).items():
            groups[g] = {
                "members": set(info.get("members", [])),
                "history": info.get("history", []),
                "avatar": info.get("avatar", "📢")
            }

        # --- PRIVATE MESSAGES ---
        for k, history in data.get("private_messages", {}).items():
            u1, u2 = k.split("|")
            private_messages[tuple(sorted((u1, u2)))] = history

        print("Data loaded")

    except Exception as e:
        print("Load error:", e)


def save_data():
    data = {
        "users": {},  # users are DB-backed now
        "groups": {
            g: {
                "members": list(info["members"]),
                "history": info["history"],
                "avatar": info["avatar"]
            }
            for g, info in groups.items()
        },
        "private_messages": {
            f"{k[0]}|{k[1]}": v for k, v in private_messages.items()
        }
    }

    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ================== INIT ==================

database.init_db()
load_data()

# ================== ROUTES ==================

@app.route("/")
def index():
    return "Chat Server Running"

@app.route("/api/users")
def get_users():
    return {"users": database.get_all_users()}

def online_payload():
    online = []
    for sid, u in active_sockets.items():
        if not any(x["username"] == u for x in online):
            online.append({
                "username": u,
                "avatar": users[u]["avatar"]
            })

    return {
        "users": online,
        "groups": [
            {"name": g, "avatar": groups[g]["avatar"]}
            for g in groups
        ]
    }

# ================== SOCKET EVENTS ==================

@socketio.on("connect")
def connect():
    print("Connected:", request.sid)

@socketio.on("disconnect")
def disconnect():
    sid = request.sid
    user = active_sockets.pop(sid, None)
    if user:
        users[user]["sid"] = None
        emit("user_list", online_payload(), broadcast=True)
        print(user, "disconnected")

@socketio.on("login")
def login(data):
    username = data.get("username")
    avatar = data.get("avatar", "👤")
    if not username:
        return

    users.setdefault(username, {})
    users[username].update({"avatar": avatar, "sid": request.sid})
    active_sockets[request.sid] = username

    database.add_user(username, avatar)

    for g, info in groups.items():
        if username in info["members"]:
            join_room(g)

    save_data()
    emit("user_list", online_payload(), broadcast=True)
    print(username, "logged in")

@socketio.on("create_group")
def create_group(data):
    name = data.get("group_name")
    avatar = data.get("avatar", "📢")
    members = set(data.get("members", []))
    creator = active_sockets.get(request.sid)

    if not name or name in groups:
        return

    members.add(creator)
    groups[name] = {"members": members, "history": [], "avatar": avatar}

    for m in members:
        if m in users and users[m]["sid"]:
            socketio.server.enter_room(users[m]["sid"], name)

    save_data()
    emit("user_list", online_payload(), broadcast=True)

@socketio.on("private_message")
def private_msg(data):
    sender = active_sockets.get(request.sid)
    to = data.get("to")
    msg = data.get("message")
    if not sender or not to or not msg:
        return

    key = tuple(sorted((sender, to)))
    private_messages.setdefault(key, []).append({"from": sender, "message": msg})
    save_data()

    if to in users and users[to]["sid"]:
        emit("private_message", {"from": sender, "message": msg}, room=users[to]["sid"])

@socketio.on("group_message")
def group_msg(data):
    sender = active_sockets.get(request.sid)
    group = data.get("group")
    msg = data.get("message")

    if group not in groups or not msg:
        return

    payload = {"from": sender, "message": msg, "group": group}
    groups[group]["history"].append(payload)
    save_data()
    emit("group_message", payload, room=group)

@socketio.on("get_history")
def history(data):
    user = active_sockets.get(request.sid)
    target = data.get("target")
    chat_type = data.get("type")

    if chat_type == "private":
        key = tuple(sorted((user, target)))
        emit("chat_history", {
            "target": target,
            "type": "private",
            "history": private_messages.get(key, [])
        })

    elif chat_type == "group" and target in groups:
        groups[target]["members"].add(user)
        join_room(target)
        save_data()
        emit("chat_history", {
            "target": target,
            "type": "group",
            "history": groups[target]["history"]
        })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=True)
