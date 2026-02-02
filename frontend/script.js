const username = sessionStorage.getItem("username");
const myAvatar = sessionStorage.getItem("avatar") || "👤";

if (!username) window.location = "login.html";

const socket = io({
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
    timeout: 20000,
    autoConnect: true
});

let activeType = null;
let activeTarget = null;
let activeAvatar = null;

let onlineUsersList = [];
let groupsList = []; // New separate list cache for filtering

// --- Config ---
const groupAvatars = ["📢", "📣", "💬", "💼", "🎮", "⚽", "🎵", "✈️", "❤️", "🔥", "✨", "🚀"];

document.getElementById("self-user").innerHTML = `<span class="avatar">${myAvatar}</span> ${username}`;

// --- Socket Events ---
let connectionStartTime = Date.now();
const CONNECTION_MSG = document.createElement("div");
CONNECTION_MSG.style.cssText = "position:fixed; top:10px; left:50%; transform:translateX(-50%); background:var(--header-bg); padding:10px 20px; border-radius:30px; box-shadow:0 4px 10px rgba(0,0,0,0.5); z-index:9999; color:var(--accent); font-weight:bold; display:none; animation: popIn 0.3s ease-out;";
CONNECTION_MSG.innerText = "Connecting...";
document.body.appendChild(CONNECTION_MSG);

socket.on("connect_error", (err) => {
    const elapsed = (Date.now() - connectionStartTime) / 1000;
    if (elapsed > 2) {
        CONNECTION_MSG.style.display = "block";
        CONNECTION_MSG.innerText = (elapsed > 10) ? "Waking up server... please wait" : "Connecting...";
    }
});

socket.on("connect", () => {
    console.log("Connected to server");
    CONNECTION_MSG.style.display = "none";
    socket.emit("login", { username: username, avatar: myAvatar });
});

socket.on("user_list", (data) => {
    onlineUsersList = data.users;
    groupsList = data.groups;

    // Initial Render (respecting filter)
    filterLists();
});

socket.on("group_created", (data) => {
    // handled by user_list update
});

socket.on("private_message", (data) => {
    if (activeType === "private" && activeTarget === data.from) {
        addMessage(data.from, data.message, false);
    }
});

socket.on("group_message", (data) => {
    if (activeType === "group" && activeTarget === data.group) {
        const isMe = data.from === username;
        const senderAvatar = findAvatar(data.from);
        const nameDisplay = senderAvatar ? `${senderAvatar} ${data.from}` : data.from;

        addMessage(data.from, data.message, isMe, nameDisplay);
    }
});

socket.on("chat_history", (data) => {
    if (data.target !== activeTarget) return;

    document.getElementById("messages").innerHTML = "";
    data.history.forEach(msg => {
        const isMe = msg.from === username;

        let nameDisplay = msg.from;
        if (data.type === 'group' && !isMe) {
            const senderAvatar = findAvatar(msg.from);
            nameDisplay = senderAvatar ? `${senderAvatar} ${msg.from}` : msg.from;
        }

        addMessage(msg.from, msg.message, isMe, (data.type === 'group' ? nameDisplay : null));
    });
    scrollToBottom();
});

// --- Search & Filter Logic ---
function filterLists() {
    const query = document.getElementById("search-input").value.toLowerCase();

    const filteredUsers = onlineUsersList.filter(u =>
        u.username !== username && u.username.toLowerCase().includes(query)
    );

    const filteredGroups = groupsList.filter(g => {
        const name = g.name || g;
        return name.toLowerCase().includes(query);
    });

    renderUserList("users", filteredUsers);
    renderGroups("groups", filteredGroups);
}

// --- Logout Logic ---
function logout() {
    sessionStorage.clear();
    window.location.href = "login.html";
}

// --- Helpers ---
function findAvatar(uname) {
    const u = onlineUsersList.find(user => user.username === uname);
    return u ? u.avatar : null;
}

// --- UI Functions ---
function renderUserList(id, users) {
    const ul = document.getElementById(id);
    ul.innerHTML = "";

    if (users.length === 0) {
        // Optional: show empty state
    }

    users.forEach(u => {
        const li = document.createElement("li");
        li.innerHTML = `<span class="avatar">${u.avatar}</span> <span>${u.username}</span>`;
        li.onclick = () => selectChat(u.username, "private", u.avatar);

        if (activeType === "private" && activeTarget === u.username) li.classList.add("active");
        ul.appendChild(li);
    });
}

function renderGroups(id, groups) {
    const ul = document.getElementById(id);
    ul.innerHTML = "";
    groups.forEach(g => {
        const name = g.name || g;
        const avatar = g.avatar || "📢";

        const li = document.createElement("li");
        li.innerHTML = `<span class="avatar">${avatar}</span> <span>${name}</span>`;
        li.onclick = () => selectChat(name, "group", avatar);

        if (activeType === "group" && activeTarget === name) li.classList.add("active");
        ul.appendChild(li);
    });
}

function selectChat(target, type, avatar) {
    activeType = type;
    activeTarget = target;
    activeAvatar = avatar;

    document.getElementById("chat-header").innerHTML = `<span class="avatar">${avatar}</span> <span>${target}</span>`;

    // Refresh lists visually to show active underline
    // We re-render to keep filter active + add active class
    // Simple way: re-call filter
    filterLists();

    socket.emit("get_history", { target: target, type: type });
    document.getElementById("messages").innerHTML = '<div style="text-align:center; padding:20px; color:#8696a0;">Loading history...</div>';
}

function addMessage(sender, text, isMe, authorName = null) {
    if (document.getElementById("messages").innerHTML.includes("Loading history...")) {
        document.getElementById("messages").innerHTML = "";
    }

    const div = document.createElement("div");
    div.className = `message ${isMe ? "sent" : "received"}`;

    if (authorName && !isMe) {
        div.innerHTML = `<div class="message-meta">${authorName}</div>`;
    }

    const content = document.createElement("div");
    content.innerText = text;
    div.appendChild(content);

    const container = document.getElementById("messages");
    container.appendChild(div);

    // Auto scroll only if already near bottom or if me
    container.scrollTop = container.scrollHeight;
}

function send() {
    const input = document.getElementById("msg");
    const msg = input.value.trim();
    if (!msg || !activeTarget) return;

    if (activeType === "private") {
        socket.emit("private_message", { to: activeTarget, message: msg });
        addMessage(username, msg, true);
    } else {
        socket.emit("group_message", { group: activeTarget, message: msg });
    }

    input.value = "";
    input.focus();
}

function handleKeyPress(event) {
    if (event.key === "Enter") send();
}

function scrollToBottom() {
    const container = document.getElementById("messages");
    container.scrollTop = container.scrollHeight;
}

// --- Modal Logic ---

function openGroupModal() {
    const modal = document.getElementById("group-modal");
    const list = document.getElementById("user-select-list");
    const avatarGrid = document.getElementById("group-avatar-grid");

    // 1. Populate Members
    list.innerHTML = "";
    onlineUsersList.forEach(u => {
        if (u.username === username) return;

        const item = document.createElement("div");
        item.className = "user-item";
        item.innerHTML = `
            <input type="checkbox" value="${u.username}" id="chk-${u.username}">
            <span class="avatar">${u.avatar}</span> 
            <span style="margin-left:10px">${u.username}</span>
        `;
        item.onclick = (e) => {
            if (e.target.type !== 'checkbox') {
                const chk = document.getElementById(`chk-${u.username}`);
                chk.checked = !chk.checked;
            }
        };
        list.appendChild(item);
    });

    if (onlineUsersList.length <= 1) {
        list.innerHTML = "<div style='color:var(--text-secondary); text-align:center;'>No other users online.</div>";
    }

    // 2. Populate Avatars
    avatarGrid.innerHTML = "";
    const hiddenInput = document.getElementById("selected-group-avatar");
    let selectedEl = null;

    groupAvatars.forEach((av, index) => {
        const el = document.createElement("div");
        el.className = "avatar-option";
        el.innerText = av;

        if (index === 0) {
            el.classList.add("selected");
            selectedEl = el;
            hiddenInput.value = av;
        }

        el.onclick = () => {
            if (selectedEl) selectedEl.classList.remove("selected");
            el.classList.add("selected");
            selectedEl = el;
            hiddenInput.value = av;
        };
        avatarGrid.appendChild(el);
    });

    modal.style.display = "flex";
    document.getElementById("new-group-name").focus();
}

function closeGroupModal() {
    document.getElementById("group-modal").style.display = "none";
}

function createGroup() {
    const name = document.getElementById("new-group-name").value.trim();
    if (!name) {
        alert("Enter a group name");
        return;
    }

    const checkboxes = document.querySelectorAll("#user-select-list input[type='checkbox']:checked");
    const members = Array.from(checkboxes).map(cb => cb.value);
    const avatar = document.getElementById("selected-group-avatar").value;

    socket.emit("create_group", { group_name: name, members: members, avatar: avatar });
    closeGroupModal();
}
