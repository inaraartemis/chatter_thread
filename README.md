# Chatters Pro

A modern real-time chat application using Python WebSockets and a custom dark-themed UI.

## Prerequisites

- [Python 3.x](https://www.python.org/downloads/)
- [pip](https://pypi.org/project/pip/) (Python package installer)

## Dependencies

You need to install the `websockets` library for the backend.

```bash
pip install websockets
```

## How to Run

### 1. Start the Backend Server

Open a terminal in the project root or `backend` folder and run:

```bash
cd backend
python server.py
```

You should see: `Server running on ws://localhost:8765`

### 2. Start the Frontend client

Simply open `frontend/index.html` in your web browser. You can maintain multiple tabs to simulate multiple users.
- On launch, accept the prompt to enter your username.
- You should see yourself and others in the sidebar.
- Start chatting!

## Troubleshooting

- **Firewall**: Ensure your firewall allows connections on port 8765.
- **WebSocket Error**: If you see connection errors in the browser console, ensure the python server is running.
