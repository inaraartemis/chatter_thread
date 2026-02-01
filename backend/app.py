from flask import Flask, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
import json
import database

app = Flask(__name__)
# Enable CORS for development
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

DATA_FILE = "data.json"

# --- Integers JSON Keys ---
# JSON only supports string keys. We must convert tuple keys to strings for storage
# and back to tuples for usage.
# Key Format: "user1|user2" (sorted)

def load_data():
    global users, groups, private_messages
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                
                saved_users = data.get("users", {})
                
                # MIGRATION: Check if these users exist in DB, if not add them
                for u, info in saved_users.items():
                    if not database.get_user(u):
                        print(f"Migrating user {u} to DB...")
                        database.add_user(u, info.get("avatar", "👤"))
                
                # Load Users from DB
                db_users = database.get_all_users()
                for u in db_users:
                    users[u["username"]] = {"avatar": u["avatar"], "sid": None}
                
                # Load Groups
                # groups structure: {name: {members: [list], history: [], avatar: ""}}
                # runtime members needs to be set
                saved_groups = data.get("groups", {})
                for g, info in saved_groups.items():
                    groups[g] = {
                        "members": set(info.get("members", [])),
                        "history": info.get("history", []),
                        "avatar": info.get("avatar", "📢")
                    }
                    
                # Load Private Messages
                # saved as {"user1|user2": []}
                # runtime as {("user1", "user2"): []}
                saved_msgs = data.get("private_messages", {})
                for key_str, history in saved_msgs.items():
                    if "|" in key_str:
                        u1, u2 = key_str.split("|")
                        private_messages[tuple(sorted((u1, u2)))] = history
                
                print("Data loaded successfully.")
        except Exception as e:
            print(f"Error loading data: {e}")

def save_data():
    # Convert runtime data to serializable format
    # Users are saved in DB.
    # To prevent wiping legacy data.json "users" field if someone restores it,
    # we can optionally read it back or just leave it empty.
    # Since we migrated on load, it's safe to write what we have or empty.
    # But to be safe against data loss if load failed:
    # Let's NOT overwrite "users" with empty dict if we can avoid it?
    # Actually, if we write the file, we overwrite it.
    # We should populate serializable_users from DB to keep data.json in sync (as a backup)
    # OR just accept it is now DB only.
    # The prompt asked for SQLite. Let's stick to DB only.
    
    serializable_users = {} 
    # (Optional: we could stop saving "users" key entirely to data.json, 
    # but keeping an empty dict or minimal data might prevent errors if we rollback)
    
    serializable_groups = {}
    for g, info in groups.items():
        serializable_groups[g] = {
            "members": list(info["members"]),
            "history": info["history"],
            "avatar": info.get("avatar")
        }
        
    serializable_msgs = {}
    for key_tuple, history in private_messages.items():
        key_str = f"{key_tuple[0]}|{key_tuple[1]}"
        serializable_msgs[key_str] = history
        
    data = {
        "users": serializable_users,
        "groups": serializable_groups,
        "private_messages": serializable_msgs
    }
    
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving data: {e}")


# In-memory storage (populated by load_data)
users = {} 
active_sockets = {}
private_messages = {}
groups = {}

# Load on startup
database.init_db()
load_data()

@app.route("/api/users")
def get_users_api():
    # Return list of all persisted users
    return {"users": database.get_all_users()}

@app.route("/")
def index():
    return "Chat Server Running"

def get_user_list():
    # Return list of user objects with avatars
    # Filter to only return ONLINE users for the list, 
    # OR return all known users? 
    # Current UI treats "users" as "Online Members".
    # Let's keep it as active sockets for presence.
    
    online_list = []
    for sid, u in active_sockets.items():
        # Get avatar from main users dict
        avatar = users[u].get("avatar", "👤")
        # Avoid duplicates
        if not any(x['username'] == u for x in online_list):
            online_list.append({"username": u, "avatar": avatar})
    
    return {
        "users": online_list,
        "groups": [{"name": g, "avatar": groups[g].get("avatar", "📢")} for g in groups]
    }

@socketio.on("connect")
def on_connect():
    print(f"Client connected: {request.sid}")

@socketio.on("disconnect")
def on_disconnect():
    sid = request.sid
    username = active_sockets.get(sid)
    if username:
        # Don't delete from 'users' dict so we persist account info (avatar)
        # Just remove from active_sockets
        if sid in active_sockets:
            del active_sockets[sid]
        
        # We also need to update user list to remove him from "Online"
        # Since 'users' dict still has him, we need to handle sid=None check?
        # My get_user_list relies on active_sockets, so it's fine.
        
        print(f"{username} disconnected")
        emit("user_list", get_user_list(), broadcast=True)

@socketio.on("login")
def on_login(data):
    username = data.get("username")
    avatar = data.get("avatar", "👤")
    
    if not username:
        return
    
    # Update or register user
    if username not in users:
        users[username] = {}
        
    users[username]["avatar"] = avatar
    users[username]["sid"] = request.sid
    
    active_sockets[request.sid] = username
    
    # Auto-join groups
    # Re-join all groups this user is a member of
    for g_name, g_info in groups.items():
        if username in g_info["members"]:
            join_room(g_name)
    
    print(f"{username} logged in")
    
    # Save to DB
    database.add_user(username, avatar)
    save_data() # Save msg/groups if any changes (though login mostly affects users)
    
    emit("user_list", get_user_list(), broadcast=True)

@socketio.on("create_group")
def on_create_group(data):
    group_name = data.get("group_name")
    group_avatar = data.get("avatar", "📢")
    members_to_add = data.get("members", [])
    creator = active_sockets.get(request.sid)
    
    if group_name and group_name not in groups:
        initial_members = {creator}
        initial_members.update(members_to_add)
        
        groups[group_name] = {
            "members": initial_members, 
            "history": [],
            "avatar": group_avatar
        }
        
        join_room(group_name)
        
        # Notify members
        emit("group_created", {"group": group_name})
        
        # Force join online members
        for member in members_to_add:
            if member in users and users[member].get("sid"):
                member_sid = users[member]["sid"]
                try:
                    socketio.server.enter_room(member_sid, group_name)
                except:
                    pass

        save_data()
        emit("user_list", get_user_list(), broadcast=True)

@socketio.on("join_group")
def on_join_group(data):
    # Only for existing groups
    pass

@socketio.on("private_message")
def on_private_message(data):
    sender = active_sockets.get(request.sid)
    recipient = data.get("to")
    message = data.get("message")
    
    if not sender or not recipient or not message:
        return

    key = tuple(sorted((sender, recipient)))
    if key not in private_messages:
        private_messages[key] = []
    
    msg_obj = {"from": sender, "message": message}
    private_messages[key].append(msg_obj)
    save_data() # Save msg
    
    if recipient in users and users[recipient].get("sid"):
        recipient_sid = users[recipient]["sid"]
        emit("private_message", {
            "from": sender,
            "message": message
        }, room=recipient_sid)

@socketio.on("group_message")
def on_group_message(data):
    sender = active_sockets.get(request.sid)
    group_name = data.get("group")
    message = data.get("message")
    
    if not sender or not group_name or not message:
        return
        
    if group_name in groups:
        msg_obj = {"from": sender, "message": message, "group": group_name}
        groups[group_name]["history"].append(msg_obj)
        save_data() # Save msg
        emit("group_message", msg_obj, room=group_name)

@socketio.on("get_history")
def on_get_history(data):
    username = active_sockets.get(request.sid)
    target = data.get("target")
    chat_type = data.get("type")
    
    history = []
    if chat_type == "private":
        key = tuple(sorted((username, target)))
        history = private_messages.get(key, [])
    elif chat_type == "group":
        if target in groups:
            # Ensure member
            if username not in groups[target]["members"]:
                groups[target]["members"].add(username)
                save_data()
            join_room(target)
            history = groups[target]["history"]
            
    emit("chat_history", {"target": target, "type": chat_type, "history": history})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # Use eventlet for proper websocket support if installed
    socketio.run(app, host="0.0.0.0", port=port, debug=True)
