import discord
from discord.ext import commands
import json
import os
import re

DB_FILE = "db.json"
FORUM_NAME = "jobs-feed"

# ===== INTENTS =====
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ===== DB =====
def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f)

# ===== MATCH (con palabra exacta) =====
def matches(content, keyword):
    return re.search(rf"\b{re.escape(keyword)}\b", content)

# ===== EVENT =====
@bot.event
async def on_thread_create(thread):
    # Solo foros
    if not isinstance(thread.parent, discord.ForumChannel):
        return

    # Solo el foro jobs-feed
    if thread.parent.name != FORUM_NAME:
        return

    try:
        starter_message = await thread.fetch_message(thread.id)
        content = starter_message.content.lower()

        db = load_db()
        mentions = set()
        matched = set()

        for user_id, keywords in db.items():
            for keyword in keywords:
                if matches(content, keyword):
                    mentions.add(f"<@{user_id}>")
                    matched.add(keyword)

        if mentions:
            msg = " ".join(mentions)
            msg += f"\n🔎 Match: {', '.join(matched)}"
            await thread.send(msg)

    except Exception as e:
        print("Error:", e)

# ===== COMMANDS =====
@bot.command()
async def subscribe(ctx, *args):
    user_id = str(ctx.author.id)
    db = load_db()

    if user_id not in db:
        db[user_id] = []

    for keyword in args:
        keyword = keyword.lower()
        if keyword not in db[user_id]:
            db[user_id].append(keyword)

    save_db(db)

    await ctx.send(f"✅ Te suscribiste a: {', '.join(db[user_id])}")

@bot.command()
async def unsubscribe(ctx, *args):
    user_id = str(ctx.author.id)
    db = load_db()

    if user_id not in db:
        return await ctx.send("No tenés suscripciones")

    for keyword in args:
        keyword = keyword.lower()
        if keyword in db[user_id]:
            db[user_id].remove(keyword)

    save_db(db)

    await ctx.send(f"🧹 Te quedan: {', '.join(db[user_id])}")

@bot.command()
async def mysubs(ctx):
    user_id = str(ctx.author.id)
    db = load_db()

    subs = db.get(user_id, [])
    await ctx.send(f"📌 Tus keywords: {', '.join(subs) if subs else 'ninguna'}")

# ===== READY =====
@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")

# ===== RUN =====
bot.run(os.getenv("DISCORD_TOKEN"))