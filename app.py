from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import sqlite3
import hashlib
import random
import os

app = Flask(__name__)
CORS(app)

DB_FILE = "scores.db"

# ---------- Database Connection Helper ----------
def get_db_connection():
    return sqlite3.connect(DB_FILE, timeout=5)

# ---------- Database Setup ----------
def init_db():
    with get_db_connection() as conn:
        c = conn.cursor()
        # Users table
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL
            )
        """)
        # Scores table
        c.execute("""
            CREATE TABLE IF NOT EXISTS scores (
                username TEXT PRIMARY KEY,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                draws INTEGER DEFAULT 0
            )
        """)
        conn.commit()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def user_exists(username):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT 1 FROM users WHERE username=?", (username,))
        return c.fetchone() is not None

# ---------- Game Logic ----------
def check_winner(board):
    win_positions = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8],
        [0, 3, 6], [1, 4, 7], [2, 5, 8],
        [0, 4, 8], [2, 4, 6]
    ]
    for pos in win_positions:
        if board[pos[0]] == board[pos[1]] == board[pos[2]] != "":
            return board[pos[0]]
    if "" not in board:
        return "draw"
    return None

def ai_move(board, ai_symbol, player_symbol):
    # Minimax AI
    best_score = -float("inf")
    best_move = None

    for i in range(9):
        if board[i] == "":
            board[i] = ai_symbol
            score = minimax(board, 0, False, ai_symbol, player_symbol)
            board[i] = ""
            if score > best_score:
                best_score = score
                best_move = i
    return best_move

def minimax(board, depth, is_maximizing, ai_symbol, player_symbol):
    winner = check_winner(board)
    if winner == ai_symbol:
        return 10 - depth
    elif winner == player_symbol:
        return depth - 10
    elif winner == "draw":
        return 0

    if is_maximizing:
        best_score = -float("inf")
        for i in range(9):
            if board[i] == "":
                board[i] = ai_symbol
                score = minimax(board, depth + 1, False, ai_symbol, player_symbol)
                board[i] = ""
                best_score = max(score, best_score)
        return best_score
    else:
        best_score = float("inf")
        for i in range(9):
            if board[i] == "":
                board[i] = player_symbol
                score = minimax(board, depth + 1, True, ai_symbol, player_symbol)
                board[i] = ""
                best_score = min(score, best_score)
        return best_score


# ---------- Routes ----------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=["POST"])
def register():
    data = request.json
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400
    if user_exists(username):
        return jsonify({"error": "Username already exists"}), 400

    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)",
                  (username, hash_password(password)))
        c.execute("INSERT INTO scores (username, wins, losses, draws) VALUES (?, 0, 0, 0)",
                  (username,))
        conn.commit()
    return jsonify({"message": "User registered successfully"})

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username", "").strip()
    password = data.get("password", "")

    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT password_hash FROM users WHERE username=?", (username,))
        row = c.fetchone()

    if not row or row[0] != hash_password(password):
        return jsonify({"error": "Invalid username or password"}), 400

    return jsonify({"message": "Login successful"})

@app.route("/move", methods=["POST"])
def move():
    data = request.json
    username = data.get("username")
    board = data.get("board")
    player_symbol = data.get("player", "X")
    ai_symbol = "O" if player_symbol == "X" else "X"

    winner = check_winner(board)
    if winner:
        update_scores(username, winner, player_symbol)
        return jsonify({"board": board, "winner": winner, "scores": get_scores()})

    ai_index = ai_move(board, ai_symbol, player_symbol)
    if ai_index is not None:
        board[ai_index] = ai_symbol

    winner = check_winner(board)
    if winner:
        update_scores(username, winner, player_symbol)

    return jsonify({"board": board, "winner": winner, "scores": get_scores()})

@app.route("/leaderboard", methods=["GET"])
def leaderboard():
    return jsonify(get_scores())

# ---------- Score helpers ----------
def update_scores(username, winner, player_symbol):
    with get_db_connection() as conn:
        c = conn.cursor()
        if winner == "draw":
            c.execute("UPDATE scores SET draws = draws + 1 WHERE username=?", (username,))
        elif winner == player_symbol:
            c.execute("UPDATE scores SET wins = wins + 1 WHERE username=?", (username,))
        else:
            c.execute("UPDATE scores SET losses = losses + 1 WHERE username=?", (username,))
        conn.commit()

def get_scores():
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT username, wins, losses, draws FROM scores ORDER BY wins DESC, draws DESC")
        rows = c.fetchall()
    return [{"username": r[0], "wins": r[1], "losses": r[2], "draws": r[3]} for r in rows]

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
