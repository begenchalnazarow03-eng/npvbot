import telebot
from telebot import types
import sqlite3
from contextlib import closing
import logging
import re

# Botuň sazlamalary
BOT_TOKEN = '8317531093:AAHgcLTi3DyFbzPj5g_B8xhq1c4-iN-r12I'
INITIAL_ADMIN_IDS = [6934292008]

bot = telebot.TeleBot(BOT_TOKEN)

# Loglamagy sazlamak
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='bot.log'
)

# Global ADMINS we BANNED
ADMINS = set()
BANNED = set()

# Maglumatlar bazasyny başlatmak
def init_db():
    with closing(sqlite3.connect('suliksponsor.db')) as conn:
        with conn:
            # Ulanyjylar tablisasy
            conn.execute('''CREATE TABLE IF NOT EXISTS users (
                                user_id INTEGER PRIMARY KEY
                            )''')
            # Sponsorlar tablisasy
            conn.execute('''CREATE TABLE IF NOT EXISTS sponsors (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                channel_id TEXT,
                                link TEXT,
                                position INTEGER
                            )''')
            # Sazlamalar tablisasy
            conn.execute('''CREATE TABLE IF NOT EXISTS settings (
                                key TEXT PRIMARY KEY,
                                value TEXT
                            )''')
            # Addlistler tablisasy
            try:
                conn.execute('''CREATE TABLE IF NOT EXISTS addlists (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    name TEXT,
                                    link TEXT,
                                    position INTEGER
                                )''')
                logging.info("Addlists tablisasy döredildi ýa-da bar.")
            except Exception as e:
                logging.error(f"Addlists tablisasy döretmekde ýalňyşlyk: {str(e)}")
                conn.execute('''DROP TABLE IF EXISTS addlists''')
                conn.execute('''CREATE TABLE addlists (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    name TEXT,
                                    link TEXT,
                                    position INTEGER
                                )''')
                logging.info("Addlists tablisasy täzeden döredildi.")

            # Adminler tablisasy
            conn.execute('''CREATE TABLE IF NOT EXISTS admins (
                                user_id INTEGER PRIMARY KEY
                            )''')
            for admin_id in INITIAL_ADMIN_IDS:
                conn.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (admin_id,))

            # Banned ulanyjylar tablisasy
            conn.execute('''CREATE TABLE IF NOT EXISTS banned_users (
                                user_id INTEGER PRIMARY KEY
                            )''')

            # Sazlamalar üçin açarlar
            conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('start_text', '')")
            conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('vpn_code', '')")

            # Köne addlist migrasiýasy
            try:
                cur = conn.execute("SELECT value FROM settings WHERE key = 'addlist'")
                addlist_value = cur.fetchone()
                if addlist_value and addlist_value[0].strip():
                    logging.info("Köne addlist açary tapyldy, göçürilýär...")
                    conn.execute("INSERT INTO addlists (name, link, position) VALUES (?, ?, NULL)", 
                                 ("Addlist", addlist_value[0].strip()))
                    conn.execute("DELETE FROM settings WHERE key = 'addlist'")
                    logging.info("Addlist üstünlikli göçürildi we köne açar pozuldy.")
            except Exception as e:
                logging.error(f"Addlist göçürmekde ýalňyşlyk: {str(e)}")

            # Sponsorlar üçin pozisiýa migrasiýasy
            try:
                cur = conn.execute("PRAGMA table_info(sponsors)")
                columns = [info[1] for info in cur.fetchall()]
                if 'position' not in columns:
                    conn.execute("ALTER TABLE sponsors ADD COLUMN position INTEGER")
                    conn.execute("UPDATE sponsors SET position = id WHERE position IS NULL")
                    logging.info("Sponsorlar tablisasyna position sütuni goşuldy we migrasiýa tamamlandy.")
            except Exception as e:
                logging.error(f"Sponsor pozisiýa migrasiýasy ýalňyşlygy: {str(e)}")

            # Addlistler üçin pozisiýa migrasiýasy
            try:
                cur = conn.execute("PRAGMA table_info(addlists)")
                columns = [info[1] for info in cur.fetchall()]
                if 'position' not in columns:
                    conn.execute("ALTER TABLE addlists ADD COLUMN position INTEGER")
                    conn.execute("UPDATE addlists SET position = id WHERE position IS NULL")
                    logging.info("Addlists tablisasyna position sütuni goşuldy we migrasiýa tamamlandy.")
            except Exception as e:
                logging.error(f"Addlist pozisiýa migrasiýasy ýalňyşlygy: {str(e)}")

init_db()

# ADMINS we BANNED ýüklemek
def load_admins():
    global ADMINS
    with closing(sqlite3.connect('suliksponsor.db')) as conn:
        cur = conn.execute("SELECT user_id FROM admins")
        ADMINS = set(row[0] for row in cur.fetchall())

def load_banned():
    global BANNED
    with closing(sqlite3.connect('suliksponsor.db')) as conn:
        cur = conn.execute("SELECT user_id FROM banned_users")
        BANNED = set(row[0] for row in cur.fetchall())

load_admins()
load_banned()

# Kömekçi funksiýalar
def get_setting(key):
    with closing(sqlite3.connect('suliksponsor.db')) as conn:
        try:
            cur = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
            res = cur.fetchone()
            return res[0] if res else ''
        except Exception as e:
            logging.error(f"Sazlama almak ýalňyşlygy (key={key}): {str(e)}")
            return ''

def set_setting(key, value):
    with closing(sqlite3.connect('suliksponsor.db')) as conn:
        try:
            with conn:
                conn.execute("UPDATE settings SET value = ? WHERE key = ?", (value, key))
        except Exception as e:
            logging.error(f"Sazlama goýmak ýalňyşlygy (key={key}): {str(e)}")

def get_sponsors():
    with closing(sqlite3.connect('suliksponsor.db')) as conn:
        try:
            cur = conn.execute("SELECT id, channel_id, link, position FROM sponsors ORDER BY position ASC")
            return cur.fetchall()
        except Exception as e:
            logging.error(f"Sponsorlary almak ýalňyşlygy: {str(e)}")
            return []

def get_addlists():
    with closing(sqlite3.connect('suliksponsor.db')) as conn:
        try:
            cur = conn.execute("SELECT id, name, link, position FROM addlists ORDER BY position ASC")
            return cur.fetchall()
        except Exception as e:
            logging.error(f"Addlistleri almak ýalňyşlygy: {str(e)}")
            return []

def get_admins():
    with closing(sqlite3.connect('suliksponsor.db')) as conn:
        try:
            cur = conn.execute("SELECT user_id FROM admins")
            return [row[0] for row in cur.fetchall()]
        except Exception as e:
            logging.error(f"Adminlary almak ýalňyşlygy: {str(e)}")
            return []

def is_user_subscribed(user_id, channel_id):
    try:
        member = bot.get_chat_member(channel_id, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logging.error(f"Kanal agzalygyny barlamak ýalňyşlygy: {str(e)}")
        return False

def get_channel_name(channel_id=None, link=None):
    try:
        if channel_id:
            chat = bot.get_chat(channel_id)
            return chat.title or f"Kanal {channel_id}"
        elif link and link.startswith('https://t.me/'):
            username = link.replace('https://t.me/', '@')
            chat = bot.get_chat(username)
            return chat.title or username
        else:
            return link.split('/')[-1] if link else "Bilinmeýän Kanal"
    except Exception as e:
        logging.error(f"Kanal adyny almakda ýalňyşlyk: {str(e)}")
        return link.split('/')[-1] if link else "Bilinmeýän Kanal"

def get_channel_id_from_link(link):
    try:
        if link.startswith('https://t.me/'):
            username = link.replace('https://t.me/', '@')
            chat = bot.get_chat(username)
            return str(chat.id)
        return None
    except Exception as e:
        logging.error(f"Kanal ID almak ýalňyşlygy: {str(e)}")
        return None

def update_channel_position(channel_type, channel_id, new_position):
    with closing(sqlite3.connect('suliksponsor.db')) as conn:
        try:
            with conn:
                # Bütin kanallary almak
                sponsors = get_sponsors()
                addlists = get_addlists()
                all_channels = []

                # Sponsorlar we addlistler birleşdirilýär
                for sponsor in sponsors:
                    if sponsor[3] is not None:  # Pozisiýasy bar bolsa
                        all_channels.append({
                            'id': sponsor[0],
                            'position': sponsor[3],
                            'type': 'sponsor',
                            'link': sponsor[2],
                            'channel_id': sponsor[1]
                        })
                for addlist in addlists:
                    if addlist[3] is not None:  # Pozisiýasy bar bolsa
                        all_channels.append({
                            'id': addlist[0],
                            'position': addlist[3],
                            'type': 'addlist',
                            'link': addlist[2],
                            'channel_id': None
                        })

                # Pozisiýa boýunça tertiplemek
                all_channels.sort(key=lambda x: x['position'])

                # Maksimum pozisiýany barlamak
                max_position = len(all_channels)
                if new_position < 1 or new_position > max_position:
                    return False, f"Ýalňyş pozisiýa! 1-den {max_position}-e çenli san iberiň."

                # Saýlanan kanaly barlaýas
                selected_channel = None
                for channel in all_channels:
                    if channel['type'] == channel_type and channel['id'] == channel_id:
                        selected_channel = channel
                        break
                if not selected_channel:
                    return False, "Kanal ýa-da addlist tapylmady!"

                # Häzirki kanalyň pozisiýasyny nollaýas
                if channel_type == 'sponsor':
                    conn.execute("UPDATE sponsors SET position = 0 WHERE id = ?", (channel_id,))
                else:
                    conn.execute("UPDATE addlists SET position = 0 WHERE id = ?", (channel_id,))

                # Täze pozisiýa goýulýar we beýleki kanallar süýşýär
                temp_channels = [ch for ch in all_channels if ch['id'] != channel_id or ch['type'] != channel_type]
                temp_channels.sort(key=lambda x: x['position'])
                
                # Täze pozisiýada kanaly ýerleşdirýäs
                new_channels = []
                inserted = False
                for i, ch in enumerate(temp_channels, 1):
                    if i == new_position and not inserted:
                        new_channels.append({
                            'id': channel_id,
                            'position': new_position,
                            'type': channel_type,
                            'link': selected_channel['link'],
                            'channel_id': selected_channel['channel_id']
                        })
                        inserted = True
                    new_channels.append({
                        'id': ch['id'],
                        'position': i if not inserted else i + 1,
                        'type': ch['type'],
                        'link': ch['link'],
                        'channel_id': ch['channel_id']
                    })
                if not inserted:
                    new_channels.append({
                        'id': channel_id,
                        'position': new_position,
                        'type': channel_type,
                        'link': selected_channel['link'],
                        'channel_id': selected_channel['channel_id']
                    })

                # Pozisiýalary täzelemek
                for i, channel in enumerate(new_channels, 1):
                    if channel['type'] == 'sponsor':
                        conn.execute("UPDATE sponsors SET position = ? WHERE id = ?", (i, channel['id']))
                    else:
                        conn.execute("UPDATE addlists SET position = ? WHERE id = ?", (i, channel['id']))

                return True, f"Kanalyň pozisiýasy üstünlikli #{new_position} üýtgedildi."
        except Exception as e:
            logging.error(f"Pozisiýa üýtgetmek ýalňyşlygy: {str(e)}")
            return False, f"Pozisiýa üýtgetmekde ýalňyşlyk: {str(e)}"

# /start buýrugy
@bot.message_handler(commands=['start'])
def start_handler(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    current_channel_id = str(message.chat.id)  # Ulanyjynyň start basan kanalynyň ID-si
    
    if user_id in BANNED:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Support", url="https://t.me/stone_tm"))
        bot.send_message(chat_id, "Siz banlandynyz", reply_markup=markup)
        return

    with closing(sqlite3.connect('suliksponsor.db')) as conn:
        try:
            with conn:
                conn.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        except Exception as e:
            logging.error(f"Ulanyjy goşmak ýalňyşlygy: {str(e)}")

    start_text = get_setting('start_text').strip()
    if not start_text:
        start_text = "Salam! VPN almak üçin aşakdaky kanallara agza boluň we Agza boldym ✅ düwmesine basin."

    # Ýerli sponsorlar we addlistler
    sponsors = get_sponsors()
    addlists = get_addlists()
    used_urls = set()
    all_channels = []

    # Sponsorlary goşmak (ulanyjynyň start basan kanaly çykarylýar)
    for sponsor in sponsors:
        if sponsor[2] not in used_urls and sponsor[3] is not None:  # Pozisiýasy bar bolsa
            # Eger ulanyjy start basan kanal ýerli sponsor bolsa, ony sanawdan aýyrýarys
            if sponsor[1] != current_channel_id:
                used_urls.add(sponsor[2])
                all_channels.append({
                    'id': sponsor[0],
                    'link': sponsor[2],
                    'position': sponsor[3],
                    'channel_id': sponsor[1],
                    'type': 'sponsor',
                    'name': get_channel_name(channel_id=sponsor[1])
                })
            else:
                logging.info(f"Ulanyjy start basan kanal ({current_channel_id}) sponsorlar arasynda bar, sanawdan aýryldy.")

    # Addlistleri goşmak
    for addlist in addlists:
        if addlist[2] not in used_urls and addlist[3] is not None:  # Pozisiýasy bar bolsa
            used_urls.add(addlist[2])
            all_channels.append({
                'id': addlist[0],
                'link': addlist[2],
                'position': addlist[3],
                'channel_id': None,
                'type': 'addlist',
                'name': addlist[1]
            })

    # Kanallary ýok bolsa
    if not all_channels:
        bot.send_message(chat_id, "Kanal ýa-da Addlist tapylmady. Admin bilen habarlaşyň.")
        return

    # Pozisiýa boýunça tertiplemek
    all_channels.sort(key=lambda x: x['position'])

    bot.send_message(chat_id, "SubGram sponsorlaryny almakda ýalňyşlyk ýüze çykdy. Ýerli kanallara agza bolup bilersiňiz.")

    # Düwmeleri döretmek - her kanal üçin aýry düwme
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []

    for i, channel in enumerate(all_channels):
        channel_name = channel['name']
        buttons.append(types.InlineKeyboardButton(channel_name, url=channel['link']))

    # Düwmeleri 2 sany setirde goýmak
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            markup.row(buttons[i], buttons[i + 1])
        else:
            markup.row(buttons[i])

    markup.add(types.InlineKeyboardButton("Agza boldym ✅", callback_data="check_sub"))
    bot.send_message(chat_id, start_text, reply_markup=markup)

# Ýerli kanallary barlamak üçin callback
@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_sub_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    logging.info(f"Check_sub callback alındy, ulanyjy ID: {user_id}")

    # Ýerli sponsorlary barlamak
    sponsors = get_sponsors()
    not_subscribed_channels = []

    for sponsor in sponsors:
        channel_id = sponsor[1]
        if not is_user_subscribed(user_id, channel_id):
            not_subscribed_channels.append(sponsor[2])

    if not_subscribed_channels:
        text = "Siz aşakdaky kanallara agza bolmadyk:\n" + "\n".join(not_subscribed_channels)
        bot.answer_callback_query(call.id, text=text, show_alert=True)
    else:
        bot.answer_callback_query(call.id, text="Siz ähli kanallara agza bolduňyz!", show_alert=True)
        vpn_code = get_setting('vpn_code')
        if vpn_code:
            bot.send_message(chat_id, f"VPN kodyňyz: {vpn_code}")
        else:
            bot.send_message(chat_id, "VPN kody heniz sazlanmady.")

# Admin paneli
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id not in ADMINS:
        bot.send_message(message.chat.id, "Siz admin däl!")
        logging.warning(f"Admin paneline rugsatsyz girmek synanyşygy: {message.from_user.id}")
        return
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ Sponsor goş", callback_data="add_sponsor"),
        types.InlineKeyboardButton("➖ Sponsor aýyr", callback_data="remove_sponsor"),
        types.InlineKeyboardButton("✏️ Start tekst üýtget", callback_data="edit_start"),
        types.InlineKeyboardButton("🔐 VPN kod üýtget", callback_data="edit_code"),
        types.InlineKeyboardButton("🔄 Sponsor ýerini çalyş", callback_data="change_sponsor_position"),
        types.InlineKeyboardButton("🔄 Addlist ýerini çalyş", callback_data="change_addlist_position"),
        types.InlineKeyboardButton("➕ Addlist goş", callback_data="add_addlist"),
        types.InlineKeyboardButton("➖ Addlist aýyr", callback_data="remove_addlist"),
        types.InlineKeyboardButton("➕ Admin goş", callback_data="add_admin"),
        types.InlineKeyboardButton("➖ Admin aýyr", callback_data="remove_admin"),
        types.InlineKeyboardButton("🚫 Ban ber", callback_data="ban_user"),
        types.InlineKeyboardButton("✅ Ban aç", callback_data="unban_user"),
        types.InlineKeyboardButton("📢 Rassylka", callback_data="broadcast"),
        types.InlineKeyboardButton("📊 Statistika", callback_data="stats")
    )
    bot.send_message(message.chat.id, "👮‍♂️ Admin paneline hoş geldiňiz", reply_markup=markup)
    logging.info(f"Admin paneli açyldy: {message.from_user.id}")

# Admin callback işleyjisi
admin_states = {}

@bot.callback_query_handler(func=lambda call: call.from_user.id in ADMINS)
def admin_callbacks(call):
    data = call.data
    user_id = call.from_user.id
    logging.info(f"Admin callback alındy: {data}, ulanyjy ID: {user_id}")

    if data == "add_sponsor":
        admin_states[user_id] = {"action": "adding_sponsor"}
        bot.send_message(user_id, "📢 Sponsor kanalyň linkini iberiň:\n\nMysal üçin: https://t.me/kanal")
        bot.answer_callback_query(call.id)

    elif data == "remove_sponsor":
        sponsors = get_sponsors()
        if not sponsors:
            bot.send_message(user_id, "Sponsor kanallary tapylmady.")
            bot.answer_callback_query(call.id)
            return
        markup = types.InlineKeyboardMarkup(row_width=2)
        for i, sponsor in enumerate(sponsors, start=1):
            channel_name = get_channel_name(channel_id=sponsor[1])
            btn = types.InlineKeyboardButton(f"{channel_name}", callback_data=f"del_sponsor_{sponsor[0]}")
            markup.add(btn)
        bot.send_message(user_id, "Aşakdaky sponsor kanallaryň birini saýlaň aýyrmak üçin:", reply_markup=markup)
        bot.answer_callback_query(call.id)

    elif data == "edit_start":
        admin_states[user_id] = {"action": "edit_start_text"}
        bot.send_message(user_id, "Täze start tekstini iberiň:")
        bot.answer_callback_query(call.id)

    elif data == "edit_code":
        admin_states[user_id] = {"action": "edit_vpn_code"}
        bot.send_message(user_id, "Täze VPN koduny iberiň:")
        bot.answer_callback_query(call.id)

    elif data == "change_sponsor_position":
        sponsors = get_sponsors()
        if not sponsors:
            bot.send_message(user_id, "Sponsor kanallary tapylmady.")
            bot.answer_callback_query(call.id)
            return
        markup = types.InlineKeyboardMarkup(row_width=2)
        for i, sponsor in enumerate(sponsors, start=1):
            channel_name = get_channel_name(channel_id=sponsor[1])
            btn = types.InlineKeyboardButton(f"{channel_name} (Poz: {sponsor[3]})", callback_data=f"select_sponsor_pos_{sponsor[0]}")
            markup.add(btn)
        bot.send_message(user_id, "Ýerini çalyşmak isleýän sponsor kanaly saýlaň:", reply_markup=markup)
        bot.answer_callback_query(call.id)

    elif data == "change_addlist_position":
        addlists = get_addlists()
        if not addlists:
            bot.send_message(user_id, "Addlist tapylmady.")
            bot.answer_callback_query(call.id)
            return
        markup = types.InlineKeyboardMarkup(row_width=2)
        for i, addlist in enumerate(addlists, start=1):
            btn = types.InlineKeyboardButton(f"{addlist[1]} (Poz: {addlist[3]})", callback_data=f"select_addlist_pos_{addlist[0]}")
            markup.add(btn)
        bot.send_message(user_id, "Ýerini çalyşmak isleýän addlisti saýlaň:", reply_markup=markup)
        bot.answer_callback_query(call.id)

    elif data == "add_addlist":
        admin_states[user_id] = {"action": "adding_addlist"}
        bot.send_message(user_id, "🔗 Addlist adyny we linkini iberiň:\n\nMysal üçin:\nAddlist ady\nhttps://t.me/kanal")
        bot.answer_callback_query(call.id)

    elif data == "remove_addlist":
        addlists = get_addlists()
        if not addlists:
            bot.send_message(user_id, "Addlist tapylmady.")
            bot.answer_callback_query(call.id)
            return
        markup = types.InlineKeyboardMarkup(row_width=2)
        for i, addlist in enumerate(addlists, start=1):
            btn = types.InlineKeyboardButton(f"{addlist[1]}", callback_data=f"del_addlist_{addlist[0]}")
            markup.add(btn)
        bot.send_message(user_id, "Aşakdaky addlistlerden birini saýlaň aýyrmak üçin:", reply_markup=markup)
        bot.answer_callback_query(call.id)

    elif data == "add_admin":
        admin_states[user_id] = {"action": "adding_admin"}
        bot.send_message(user_id, "Täze admin ID giriziň:")
        bot.answer_callback_query(call.id)

    elif data == "remove_admin":
        admins = get_admins()
        if len(admins) <= 1:
            bot.send_message(user_id, "Iň bolmanda bir admin galmaly!")
            bot.answer_callback_query(call.id)
            return
        markup = types.InlineKeyboardMarkup(row_width=1)
        for admin_id in admins:
            try:
                user = bot.get_chat(admin_id)
                name = f"@{user.username}" if user.username else user.first_name or "Unknown"
            except:
                name = "Unknown"
            btn = types.InlineKeyboardButton(f"{name} ({admin_id})", callback_data=f"del_admin_{admin_id}")
            markup.add(btn)
        bot.send_message(user_id, "Haysy admin aýyrmaly:", reply_markup=markup)
        bot.answer_callback_query(call.id)

    elif data == "ban_user":
        admin_states[user_id] = {"action": "banning_user"}
        bot.send_message(user_id, "Haysy ID banlamaly:")
        bot.answer_callback_query(call.id)

    elif data == "unban_user":
        admin_states[user_id] = {"action": "unbanning_user"}
        bot.send_message(user_id, "Haysy ID unban etmeli:")
        bot.answer_callback_query(call.id)

    elif data == "broadcast":
        admin_states[user_id] = {"action": "broadcast_text", "data": {"text": "", "photo": None, "buttons": []}}
        bot.send_message(user_id, "Rassylka üçin tekst ýa-da habar iberiň:")
        bot.answer_callback_query(call.id)

    elif data == "stats":
        with closing(sqlite3.connect('suliksponsor.db')) as conn:
            try:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM users")
                users_count = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM sponsors")
                sponsors_count = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM addlists")
                addlists_count = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM admins")
                admins_count = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM banned_users")
                banned_count = cur.fetchone()[0]
                bot.send_message(user_id, f"📊 Statistika:\n👥 Ulanyjylar: {users_count}\n📢 Sponsorlar: {sponsors_count}\n🔗 Addlistler: {addlists_count}\n👮 Adminlar: {admins_count}\n🚫 Banlananlar: {banned_count}")
                bot.answer_callback_query(call.id)
            except Exception as e:
                logging.error(f"Statistika ýalňyşlygy: {str(e)}")
                bot.send_message(user_id, "Statistikany almakda ýalňyşlyk ýüze çykdy.")
                bot.answer_callback_query(call.id)

    elif data.startswith("del_sponsor_"):
        sponsor_id = int(data.split("_")[-1])
        with closing(sqlite3.connect('suliksponsor.db')) as conn:
            try:
                with conn:
                    conn.execute("DELETE FROM sponsors WHERE id = ?", (sponsor_id,))
                    # Pozisiýalary täzelemek
                    sponsors = get_sponsors()
                    for i, sponsor in enumerate(sponsors, 1):
                        conn.execute("UPDATE sponsors SET position = ? WHERE id = ?", (i, sponsor[0]))
                bot.answer_callback_query(call.id, f"Sponsor №{sponsor_id} üstünlikli aýryldy.")
                bot.edit_message_reply_markup(user_id, call.message.message_id, reply_markup=None)
            except Exception as e:
                logging.error(f"Sponsor pozmak ýalňyşlygy: {str(e)}")
                bot.answer_callback_query(call.id, "Sponsor pozmakda ýalňyşlyk ýüze çykdy.")

    elif data.startswith("del_addlist_"):
        addlist_id = int(data.split("_")[-1])
        with closing(sqlite3.connect('suliksponsor.db')) as conn:
            try:
                with conn:
                    conn.execute("DELETE FROM addlists WHERE id = ?", (addlist_id,))
                    # Pozisiýalary täzelemek
                    addlists = get_addlists()
                    for i, addlist in enumerate(addlists, 1):
                        conn.execute("UPDATE addlists SET position = ? WHERE id = ?", (i, addlist[0]))
                bot.answer_callback_query(call.id, f"Addlist №{addlist_id} üstünlikli aýryldy.")
                bot.edit_message_reply_markup(user_id, call.message.message_id, reply_markup=None)
            except Exception as e:
                logging.error(f"Addlist pozmak ýalňyşlygy: {str(e)}")
                bot.answer_callback_query(call.id, "Addlist pozmakda ýalňyşlyk ýüze çykdy.")

    elif data.startswith("del_admin_"):
        admin_id = int(data.split("_")[-1])
        if admin_id == user_id:
            bot.answer_callback_query(call.id, "Özüňizi aýryp bilmeýärsiňiz!")
            return
        with closing(sqlite3.connect('suliksponsor.db')) as conn:
            try:
                with conn:
                    conn.execute("DELETE FROM admins WHERE user_id = ?", (admin_id,))
                load_admins()
                bot.answer_callback_query(call.id, f"Admin {admin_id} aýryldy.")
                bot.edit_message_reply_markup(user_id, call.message.message_id, reply_markup=None)
            except Exception as e:
                logging.error(f"Admin pozmak ýalňyşlygy: {str(e)}")
                bot.answer_callback_query(call.id, "Admin pozmakda ýalňyşlyk ýüze çykdy.")

    elif data.startswith("select_sponsor_pos_"):
        sponsor_id = int(data.split("_")[-1])
        admin_states[user_id] = {"action": "set_sponsor_position", "sponsor_id": sponsor_id}
        bot.send_message(user_id, "Täze pozisiýany (san, meselem, 1, 2, 3...) iberiň:")
        bot.answer_callback_query(call.id)

    elif data.startswith("select_addlist_pos_"):
        addlist_id = int(data.split("_")[-1])
        admin_states[user_id] = {"action": "set_addlist_position", "addlist_id": addlist_id}
        bot.send_message(user_id, "Täze pozisiýany (san, meselem, 1, 2, 3...) iberiň:")
        bot.answer_callback_query(call.id)

# Admin habar işleyjisi
@bot.message_handler(content_types=['text', 'photo'], func=lambda m: m.from_user.id in ADMINS)
def admin_message_handler(message):
    user_id = message.from_user.id
    if user_id not in admin_states:
        return

    state = admin_states[user_id]
    logging.info(f"Admin habar alındy: {message.text if message.text else 'Surat'}, action: {state['action']}")

    if state["action"] == "adding_sponsor":
        text = message.text.strip()
        try:
            if not text.startswith('https://t.me/'):
                bot.send_message(user_id, "Ýalňyş link. Link 'https://t.me/' bilen başlamaly:\n\nMysal: https://t.me/kanal")
                return
            
            # Kanal ID'sini awtomatik almak
            channel_id = get_channel_id_from_link(text)
            if not channel_id:
                bot.send_message(user_id, "Kanal ID alynmady. Linkiň dogrudygyny barlaň we botyň kanala admin edilendigine göz ýetiriň.")
                return
            
            try:
                chat = bot.get_chat(channel_id)
                if chat.type not in ['channel', 'supergroup']:
                    bot.send_message(user_id, "Bu kanal ýa-da supergroup däl!")
                    return
            except Exception as e:
                bot.send_message(user_id, f"Kanal tapylmady ýa-da botda ýeterlik rugsat ýok: {str(e)}")
                return
            
            with closing(sqlite3.connect('suliksponsor.db')) as conn:
                try:
                    with conn:
                        # Täze kanaly soňky pozisiýa bilen goşmak
                        cur = conn.execute("SELECT MAX(position) FROM sponsors")
                        max_position = cur.fetchone()[0] or 0
                        conn.execute("INSERT INTO sponsors (channel_id, link, position) VALUES (?, ?, ?)", 
                                    (channel_id, text, max_position + 1))
                    bot.send_message(user_id, f"✅ Sponsor kanal üstünlikli goşuldy:\nID: {channel_id}\nLink: {text}\nAdy: {get_channel_name(channel_id=channel_id)}")
                    admin_states.pop(user_id)
                except Exception as e:
                    logging.error(f"Sponsor goşmak ýalňyşlygy: {str(e)}")
                    bot.send_message(user_id, f"Sponsor goşmakda ýalňyşlyk: {str(e)}")
        except Exception as e:
            bot.send_message(user_id, f"Ýalňyş maglumat! Linki dogry görnüşde iberiň:\n\nMysal: https://t.me/kanal\n\nÝalňyşlyk: {str(e)}")
            logging.error(f"Sponsor goşmak ýalňyşlygy: {str(e)}")

    elif state["action"] == "edit_start_text":
        try:
            set_setting('start_text', message.text.strip())
            bot.send_message(user_id, "✅ Start teksti üstünlikli üýtgedildi.")
            admin_states.pop(user_id)
        except Exception as e:
            logging.error(f"Start tekst üýtgetmek ýalňyşlygy: {str(e)}")
            bot.send_message(user_id, f"Start tekst üýtgetmekde ýalňyşlyk: {str(e)}")

    elif state["action"] == "edit_vpn_code":
        try:
            set_setting('vpn_code', message.text.strip())
            bot.send_message(user_id, "✅ VPN kody üstünlikli üýtgedildi.")
            admin_states.pop(user_id)
        except Exception as e:
            logging.error(f"VPN kod üýtgetmek ýalňyşlygy: {str(e)}")
            bot.send_message(user_id, f"VPN kod üýtgetmekde ýalňyşlyk: {str(e)}")

    elif state["action"] == "set_sponsor_position":
        try:
            new_position = int(message.text.strip())
            success, msg = update_channel_position('sponsor', state["sponsor_id"], new_position)
            bot.send_message(user_id, msg)
            if success:
                admin_states.pop(user_id)
        except ValueError:
            bot.send_message(user_id, "San iberiň (meselem, 1, 2, 3...)")
        except Exception as e:
            logging.error(f"Sponsor pozisiýasyny üýtgetmek ýalňyşlygy: {str(e)}")
            bot.send_message(user_id, f"Sponsor pozisiýasyny üýtgetmekde ýalňyşlyk: {str(e)}")

    elif state["action"] == "set_addlist_position":
        try:
            new_position = int(message.text.strip())
            success, msg = update_channel_position('addlist', state["addlist_id"], new_position)
            bot.send_message(user_id, msg)
            if success:
                admin_states.pop(user_id)
        except ValueError:
            bot.send_message(user_id, "San iberiň (meselem, 1, 2, 3...)")
        except Exception as e:
            logging.error(f"Addlist pozisiýasyny üýtgetmek ýalňyşlygy: {str(e)}")
            bot.send_message(user_id, f"Addlist pozisiýasyny üýtgetmekde ýalňyşlyk: {str(e)}")

    elif state["action"] == "adding_addlist":
        text = message.text.strip()
        try:
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            if len(lines) != 2:
                bot.send_message(user_id, "Ýalňyş format. Addlist adyny we linkini iki setirde iberiň:\n\nMysal:\nAddlist ady\nhttps://t.me/kanal")
                return
            name, link = lines
            if not link.startswith('https://t.me/'):
                bot.send_message(user_id, "Ýalňyş link. Link 'https://t.me/' bilen başlamaly:\n\nMysal:\nAddlist ady\nhttps://t.me/kanal")
                return
            with closing(sqlite3.connect('suliksponsor.db')) as conn:
                try:
                    with conn:
                        # Täze addlisti soňky pozisiýa bilen goşmak
                        cur = conn.execute("SELECT MAX(position) FROM addlists")
                        max_position = cur.fetchone()[0] or 0
                        conn.execute("INSERT INTO addlists (name, link, position) VALUES (?, ?, ?)", (name, link, max_position + 1))
                    bot.send_message(user_id, f"✅ Addlist üstünlikli goşuldy:\nAdy: {name}\nLink: {link}")
                    admin_states.pop(user_id)
                except Exception as e:
                    logging.error(f"Addlist goşmak ýalňyşlygy: {str(e)}")
                    bot.send_message(user_id, f"Addlist goşmakda ýalňyşlyk: {str(e)}")
        except Exception as e:
            bot.send_message(user_id, f"Ýalňyş maglumat! Addlist adyny we linkini dogry görnüşde iberiň:\n\nMysal:\nAddlist ady\nhttps://t.me/kanal\n\nÝalňyşlyk: {str(e)}")
            logging.error(f"Addlist goşmak ýalňyşlygy: {str(e)}")

    elif state["action"] == "adding_admin":
        try:
            new_id = int(message.text.strip())
            with closing(sqlite3.connect('suliksponsor.db')) as conn:
                with conn:
                    conn.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (new_id,))
            load_admins()
            bot.send_message(user_id, "Täze admin goşuldy.")
            admin_states.pop(user_id)
        except ValueError:
            bot.send_message(user_id, "Dogry ID giriziň (san).")
        except Exception as e:
            logging.error(f"Admin goşmak ýalňyşlygy: {str(e)}")
            bot.send_message(user_id, f"Admin goşmakda ýalňyşlyk: {str(e)}")

    elif state["action"] == "banning_user":
        try:
            ban_id = int(message.text.strip())
            with closing(sqlite3.connect('suliksponsor.db')) as conn:
                with conn:
                    conn.execute("INSERT OR IGNORE INTO banned_users (user_id) VALUES (?)", (ban_id,))
            load_banned()
            bot.send_message(user_id, "Ulanyjy banlandy.")
            admin_states.pop(user_id)
        except ValueError:
            bot.send_message(user_id, "Dogry ID giriziň (san).")
        except Exception as e:
            logging.error(f"Ban bermek ýalňyşlygy: {str(e)}")
            bot.send_message(user_id, f"Ban bermekde ýalňyşlyk: {str(e)}")

    elif state["action"] == "unbanning_user":
        try:
            unban_id = int(message.text.strip())
            with closing(sqlite3.connect('suliksponsor.db')) as conn:
                with conn:
                    conn.execute("DELETE FROM banned_users WHERE user_id = ?", (unban_id,))
            load_banned()
            bot.send_message(user_id, "Ulanyjy ban açyldy.")
            admin_states.pop(user_id)
        except ValueError:
            bot.send_message(user_id, "Dogry ID giriziň (san).")
        except Exception as e:
            logging.error(f"Ban açmak ýalňyşlygy: {str(e)}")
            bot.send_message(user_id, f"Ban açmakda ýalňyşlyk: {str(e)}")

    elif state["action"] == "broadcast_text":
        try:
            state["data"]["text"] = message.text.strip()
            state["action"] = "broadcast_photo"
            bot.send_message(user_id, "Rassylka üçin surat ýükläň (ýa-da surat gerek däl bolsa, 'Geç' diýip ýazyň):")
        except Exception as e:
            logging.error(f"Broadcast tekst ýalňyşlygy: {str(e)}")
            bot.send_message(user_id, f"Broadcast tekst işlemekde ýalňyşlyk: {str(e)}")

    elif state["action"] == "broadcast_photo":
        try:
            if message.text and message.text.strip().lower() == "geç":
                state["action"] = "broadcast_buttons"
                state["data"]["photo"] = None
                bot.send_message(user_id, "Knopka goşmak isleýärsiňizmi? (Ýa-da 'Tamam' diýip ýazyň):\nKnopka adyny we linkini şu görnüşde iberiň:\n\nKnopka ady\nhttps://t.me/kanal")
            elif message.photo:
                state["data"]["photo"] = message.photo[-1].file_id
                state["action"] = "broadcast_buttons"
                bot.send_message(user_id, "Knopka goşmak isleýärsiňizmi? (Ýa-da 'Tamam' diýip ýazyň):\nKnopka adyny we linkini şu görnüşde iberiň:\n\nKnopka ady\nhttps://t.me/kanal")
            else:
                bot.send_message(user_id, "Surat ýükläň ýa-da 'Geç' diýip ýazyň.")
        except Exception as e:
            logging.error(f"Broadcast surat ýalňyşlygy: {str(e)}")
            bot.send_message(user_id, f"Broadcast surat işlemekde ýalňyşlyk: {str(e)}")

    elif state["action"] == "broadcast_buttons":
        try:
            if message.text and message.text.strip().lower() == "tamam":
                with closing(sqlite3.connect('suliksponsor.db')) as conn:
                    try:
                        cur = conn.execute("SELECT user_id FROM users")
                        users = cur.fetchall()
                        count = 0
                        markup = types.InlineKeyboardMarkup(row_width=2)
                        for btn in state["data"]["buttons"]:
                            markup.add(types.InlineKeyboardButton(btn["name"], url=btn["link"]))

                        for u in users:
                            try:
                                if state["data"]["photo"]:
                                    bot.send_photo(u[0], state["data"]["photo"], caption=state["data"]["text"], reply_markup=markup)
                                else:
                                    bot.send_message(u[0], state["data"]["text"], reply_markup=markup)
                                count += 1
                            except Exception as e:
                                logging.error(f"Rassylka ýalňyşlygy, ulanyjy {u[0]}: {str(e)}")
                        bot.send_message(user_id, f"Rassylka {count} ulanyja ugradyldy.")
                        admin_states.pop(user_id)
                    except Exception as e:
                        logging.error(f"Rassylka ýalňyşlygy (maglumat bazasy): {str(e)}")
                        bot.send_message(user_id, f"Rassylka ýerine ýetirmekde ýalňyşlyk: {str(e)}")
            else:
                text = message.text.strip()
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                if len(lines) != 2:
                    bot.send_message(user_id, "Ýalňyş format. Knopka adyny we linkini iki setirde iberiň:\n\nKnopka ady\nhttps://t.me/kanal")
                    return
                name, link = lines
                if not link.startswith('https://'):
                    bot.send_message(user_id, "Ýalňyş link. Link 'https://' bilen başlamaly:\n\nKnopka ady\nhttps://t.me/kanal")
                    return
                state["data"]["buttons"].append({"name": name, "link": link})
                bot.send_message(user_id, f"Knopka goşuldy: {name}\nBaşga knopka goşmak isleýärsiňizmi? (Ýa-da 'Tamam' diýip ýazyň):")
        except Exception as e:
            logging.error(f"Broadcast knopka ýalňyşlygy: {str(e)}")
            bot.send_message(user_id, f"Broadcast knopka işlemekde ýalňyşlyk: {str(e)}")

if __name__ == "__main__":
    try:
        logging.info("Bot işläp başlady")
        bot.infinity_polling()
    except telebot.apihelper.ApiTelegramException as e:
        if e.error_code == 409:
            logging.error("Ýalňyşlyk: Başga bot nusgasy işleýär. Diňe bir nusganyň işläp durandygyna göz ýetiriň.")
            for admin_id in ADMINS:
                try:
                    bot.send_message(admin_id, "Ýalňyşlyk: Başga bot nusgasy işleýär. Diňe bir nusganyň işläp durandygyna göz ýetiriň.")
                except:
                    pass
        else:
            logging.error(f"Botuň işinde ýalňyşlyk: {str(e)}")
            for admin_id in ADMINS:
                try:
                    bot.send_message(admin_id, f"Botuň işinde ýalňyşlyk: {str(e)}")
                except:
                    pass
            raise e
    except Exception as e:
        logging.error(f"Umumy ýalňyşlyk: {str(e)}")
        for admin_id in ADMINS:
            try:
                bot.send_message(admin_id, f"Botuň işinde ýalňyşlyk: {str(e)}")
            except:
                pass
        raise e
