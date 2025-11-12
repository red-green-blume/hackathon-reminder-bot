import sqlite3


def create_database(name):
    if ".db" in name:
        conn = sqlite3.connect(f"{name}")
    else:
        conn = sqlite3.connect(f"{name}.db")
    conn.close()


def create_tables(db_name):
    conn = sqlite3.connect(f"{db_name}")
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id TEXT,
            username TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS game_session (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id BIGINT,
            created_by TEXT,
            session_status TEXT,
            created_at DATETIME,
            started_at DATETIME,
            finished_at DATETIME,
            last_word_user_id BIGINT DEFAULT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS words (
            en TEXT UNIQUE,
            ru TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leaders (
            chat_id INTEGER,
            user_id BIGINT,
            score INTEGER DEFAULT 0,
            game_played INTEGER DEFAULT 0,
            PRIMARY KEY (chat_id, user_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS game_players (
            session_id INTEGER,
            user_id BIGINT,
            order_join INTEGER,
            is_active INTEGER 
        )
    ''')


def delete_table(db_name, table_name):
    conn = sqlite3.connect(f"{db_name}")
    cursor = conn.cursor()
    cursor.execute(f"DROP TABLE IF EXISTS {table_name}")


def add_or_update_user(db_name, tg_id, username):
    conn = sqlite3.connect(f"{db_name}")
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE tg_id = ?", (tg_id,))
    existing = cursor.fetchone()

    if existing:
        cursor.execute("UPDATE users SET username = ? WHERE tg_id = ?", (username, tg_id))
    else:
        cursor.execute("INSERT INTO users (tg_id, username) VALUES (?, ?)", (tg_id, username))

    conn.commit()
    conn.close()


def add_game_session(db_name, chat_id, created_by):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO game_session (chat_id, created_by, session_status, created_at)
        VALUES (?, ?, ?, datetime('now'))
    ''', (chat_id, created_by, 'waiting'))

    conn.commit()
    session_id = cursor.lastrowid

    cursor.execute('''
        INSERT INTO game_players (session_id, user_id, order_join, is_active)
        VALUES (?, ?, ?, 1)
    ''', (session_id, created_by, 1))

    conn.commit()
    conn.close()
    return session_id


def update_game_start(db_name, session_id):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE game_session
        SET session_status = 'started',
            started_at = datetime('now')
        WHERE id = ?
    ''', (session_id,))

    conn.commit()
    conn.close()


def update_game_finish(db_name, session_id):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE game_session
        SET session_status = 'finished',
            finished_at = datetime('now')
        WHERE id = ?
    ''', (session_id,))

    conn.commit()
    conn.close()

def add_game_player(db_name, session_id, user_id, order_join):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT is_active FROM game_players
        WHERE session_id = ? AND user_id = ?
    ''', (session_id, user_id))
    existing = cursor.fetchone()

    if existing is None:
        cursor.execute('''
            INSERT INTO game_players (session_id, user_id, order_join, is_active)
            VALUES (?, ?, ?, 1)
        ''', (session_id, user_id, order_join))
    else:
        cursor.execute('''
            UPDATE game_players
            SET is_active = 1
            WHERE session_id = ? AND user_id = ?
        ''', (session_id, user_id))

    conn.commit()
    conn.close()


def deactivate_game_player(db_name, session_id, user_id):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE game_players
        SET is_active = 0
        WHERE session_id = ? AND user_id = ?
    ''', (session_id, user_id))

    conn.commit()
    conn.close()


def clear_database(db_name):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    tables = ['users', 'game_session', 'leaders', 'game_players']
    # tables = ['users', 'game_session', 'leaders', 'game_players', 'words']

    for table in tables:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")

    create_tables(db_name)
    conn.commit()
    conn.close()


def get_active_session(db_name, chat_id):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id FROM game_session
        WHERE chat_id = ? AND session_status != 'finished'
    ''', (chat_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def get_random_word(db_name):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute('SELECT en, ru FROM words ORDER BY RANDOM() LIMIT 1')
    result = cursor.fetchone()
    conn.close()
    return result if result else ("hello", "привет")


def check_word_exists(db_name, word):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute('SELECT ru FROM words WHERE en = ?', (word.lower(),))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None


def get_next_player(db_name, session_id, current_player_id):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT user_id, order_join 
        FROM game_players 
        WHERE session_id = ? AND is_active = 1 
        ORDER BY order_join
    ''', (session_id,))

    players = cursor.fetchall()
    conn.close()

    if not players:
        return None

    current_index = None
    for i, (user_id, order) in enumerate(players):
        if user_id == current_player_id:
            current_index = i
            break

    if current_index is None:
        return players[0][0]

    next_index = (current_index + 1) % len(players)
    return players[next_index][0]


def get_player_name(db_name, user_id):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute('SELECT username FROM users WHERE tg_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else f"Игрок {user_id}"


def get_active_players(db_name, session_id):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT user_id FROM game_players 
        WHERE session_id = ? AND is_active = 1
    ''', (session_id,))
    players = [row[0] for row in cursor.fetchall()]
    conn.close()
    return players


def update_last_word(db_name, session_id, user_id, word):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE game_session 
        SET last_word_user_id = ? 
        WHERE id = ?
    ''', (user_id, session_id))
    conn.commit()
    conn.close()


def get_session_status(db_name, session_id):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute("SELECT session_status FROM game_session WHERE id = ?", (session_id,))
    result = cursor.fetchone()
    conn.close()
    status = result[0] if result else None
    return status


def get_winner_and_update_leaders(db_name, session_id):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    try:
        cursor.execute('''
            SELECT last_word_user_id, chat_id, created_by 
            FROM game_session 
            WHERE id = ? AND session_status = 'finished'
        ''', (session_id,))
        game_data = cursor.fetchone()

        if not game_data:
            return None

        last_word_user_id, chat_id, created_by = game_data

        if last_word_user_id:
            winner_id = last_word_user_id

            cursor.execute('''
                INSERT INTO leaders (chat_id, user_id, score, game_played)
                VALUES (?, ?, 1, 1)
                ON CONFLICT(chat_id, user_id) 
                DO UPDATE SET 
                    score = score + 1,
                    game_played = game_played + 1
            ''', (chat_id, winner_id))

            cursor.execute('SELECT username FROM users WHERE tg_id = ?', (winner_id,))
            winner_name = cursor.fetchone()
            winner_name = winner_name[0] if winner_name else f"Игрок {winner_id}"

            conn.commit()
            return winner_name

        return None

    except Exception as e:
        # print(f"Ошибка при определении победителя: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()


def update_games_played_for_all_players(db_name, session_id, chat_id):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    try:
        cursor.execute('''
            SELECT user_id FROM game_players 
            WHERE session_id = ? AND is_active = 1
        ''', (session_id,))

        players = cursor.fetchall()

        for (user_id,) in players:
            cursor.execute('''
                INSERT INTO leaders (chat_id, user_id, score, game_played)
                VALUES (?, ?, 0, 1)
                ON CONFLICT(chat_id, user_id) 
                DO UPDATE SET game_played = game_played + 1
            ''', (chat_id, user_id))

        conn.commit()

    except Exception as e:
        # print(f"Ошибка при обновлении счетчика игр: {e}")
        conn.rollback()
    finally:
        conn.close()


def check_and_finish_expired_games(db_name):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    try:
        cursor.execute('''
            SELECT id, chat_id, started_at, last_word_user_id 
            FROM game_session 
            WHERE session_status = 'started' 
            AND datetime(started_at) < datetime('now', '-10 minutes')
        ''')
        expired_games = cursor.fetchall()

        finished_games = []

        for game_id, chat_id, started_at, last_word_user_id in expired_games:
            cursor.execute('''
                UPDATE game_session 
                SET session_status = 'finished', finished_at = datetime('now')
                WHERE id = ?
            ''', (game_id,))

            if last_word_user_id:
                cursor.execute('''
                    INSERT INTO leaders (chat_id, user_id, score, game_played)
                    VALUES (?, ?, 1, 1)
                    ON CONFLICT(chat_id, user_id) 
                    DO UPDATE SET 
                        score = score + 1,
                        game_played = game_played + 1
                ''', (chat_id, last_word_user_id))

            finished_games.append((game_id, chat_id, last_word_user_id))

        conn.commit()
        return finished_games

    except Exception as e:
        # print(f"Ошибка при завершении игр: {e}")
        conn.rollback()
        return []
    finally:
        conn.close()


if __name__ == "__main__":
    # print()
    # create_database("words_game.db")
    # create_tables("words_game.db")
    # delete_table("words_game.db", "game_session")
    clear_database("words_game.db")
