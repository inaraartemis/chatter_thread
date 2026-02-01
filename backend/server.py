import asyncio
import json
import websockets

users = {}          # username -> websocket
groups = {"General": set()}

async def send_user_list():
    data = json.dumps({
        "type": "users",
        "users": list(users.keys()),
        "groups": list(groups.keys())
    })
    for ws in users.values():
        await ws.send(data)

async def handler(ws):
    username = None
    try:
        login_data = json.loads(await ws.recv())
        username = login_data["username"]

        users[username] = ws
        groups["General"].add(username)
        print(username, "connected")

        await send_user_list()

        async for message in ws:
            data = json.loads(message)

            # One-to-one chat
            if data["type"] == "private":
                to = data["to"]
                if to in users:
                    await users[to].send(json.dumps({
                        "type": "private",
                        "from": username,
                        "message": data["message"]
                    }))

            # Group chat
            if data["type"] == "group":
                group = data["group"]
                for member in groups.get(group, []):
                    if member != username:
                        await users[member].send(json.dumps({
                            "type": "group",
                            "from": username,
                            "group": group,
                            "message": data["message"]
                        }))

    finally:
        if username:
            users.pop(username, None)
            for g in groups.values():
                g.discard(username)
            await send_user_list()
            print(username, "disconnected")

async def main():
    async with websockets.serve(handler, "localhost", 8765):
        print("Server running on ws://localhost:8765")
        await asyncio.Future()

asyncio.run(main())
