import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import re

# ===== CONFIG =====
DB_FILE = "db.json"
FORUM_NAME = "jobs-feed"

GUILD_ID = int(os.getenv("GUILD_ID"))
JOBS_CHANNEL_ID = int(os.getenv("JOBS_CHANNEL_ID"))

# ===== INTENTS =====
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ===== DATABASE =====
def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f)

# ===== SYNONYMS =====
SYNONYMS = {
    "jr": "junior",
    "sr": "senior",
    "ssr": "semi senior",
    "node": "nodejs",
    "reactjs": "react",
}

def normalize_word(word):
    """Normalize a word using synonyms dictionary"""
    return SYNONYMS.get(word, word)

# ===== MATCHING =====
def matches_query(content, query):
    """
    Match ALL words inside a query (AND logic)
    Applies synonym normalization
    """
    words = query.lower().split()
    normalized_words = [normalize_word(w) for w in words]

    return all(
        re.search(rf"\b{re.escape(word)}\b", content)
        for word in normalized_words
    )

# ===== UI COMPONENTS =====
class SearchView(discord.ui.View):
    def __init__(self, guild_id, channel_id, user_id, keyword):
        super().__init__(timeout=120)

        self.user_id = str(user_id)
        self.keyword = keyword.lower()

        url = f"https://discord.com/channels/{guild_id}/{channel_id}"

        self.add_item(discord.ui.Button(
            label="Ver todas las ofertas",
            style=discord.ButtonStyle.link,
            url=url
        ))

        self.add_item(MySubsButton())
        self.add_item(CancelButton(self.user_id, self.keyword))


class MySubsButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Ver mis suscripciones",
            style=discord.ButtonStyle.secondary
        )

    async def callback(self, interaction: discord.Interaction):
        db = load_db()
        subs = db.get(str(interaction.user.id), [])

        await interaction.response.send_message(
            f"📌 Tus palabras clave: {', '.join(subs) if subs else 'ninguna'}",
            ephemeral=True
        )


class CancelButton(discord.ui.Button):
    def __init__(self, user_id, keyword):
        super().__init__(
            label="Cancelar",
            style=discord.ButtonStyle.danger
        )
        self.user_id = user_id
        self.keyword = keyword

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message(
                "No puedes usar este botón",
                ephemeral=True
            )

        db = load_db()

        if self.user_id in db and self.keyword in db[self.user_id]:
            db[self.user_id].remove(self.keyword)
            save_db(db)

            await interaction.response.edit_message(
                content=f"🧹 Removiste **{self.keyword}** de tus suscripciones",
                view=None
            )
        else:
            await interaction.response.send_message(
                "Suscripción no encontrada",
                ephemeral=True
            )

# ===== EVENT: NEW THREADS =====
@bot.event
async def on_thread_create(thread):
    print("🔥 THREAD DETECTED:", thread.parent.name)

    if not isinstance(thread.parent, discord.ForumChannel):
        return

    if thread.parent.name != FORUM_NAME:
        return

    try:
        starter_message = await thread.fetch_message(thread.id)
        content = starter_message.content.lower()

        db = load_db()
        mentions = set()
        matched = set()

        for user_id, queries in db.items():
            for query in queries:
                if matches_query(content, query):
                    mentions.add(f"<@{user_id}>")
                    matched.add(query)

        if mentions:
            msg = " ".join(mentions)
            msg += f"\n🔎 Coincidencia: {', '.join(matched)}"
            await thread.send(msg)

    except Exception as e:
        print("Error:", e)

# ===== SLASH COMMANDS =====
@tree.command(name="subscribe", description="Subscribe to job alerts")
@app_commands.describe(keyword="Example: python junior, js ssr")
async def subscribe(interaction: discord.Interaction, keyword: str):
    user_id = str(interaction.user.id)
    db = load_db()

    if user_id not in db:
        db[user_id] = []

    keyword = keyword.lower()

    if keyword not in db[user_id]:
        db[user_id].append(keyword)

    save_db(db)

    view = SearchView(
        interaction.guild.id,
        JOBS_CHANNEL_ID,
        interaction.user.id,
        keyword
    )

    await interaction.response.send_message(
        f"""✅ {interaction.user.mention} ahora estás suscrito a **{keyword}**

🔔 Se te notificará cuando una oferta contenga **todas** las palabras de esta búsqueda.

💡 Ejemplo:
Si usás `python jr`, también matcheará con `python junior`.

Para explorar las ofertas actuales:
usa el buscador dentro del foro `jobs-feed`.
""",
        view=view
    )


@tree.command(name="unsubscribe", description="Remove a subscription")
@app_commands.describe(keyword="Keyword to remove")
async def unsubscribe(interaction: discord.Interaction, keyword: str):
    user_id = str(interaction.user.id)
    db = load_db()

    if user_id not in db:
        return await interaction.response.send_message("No se encontraron suscripciones")

    keyword = keyword.lower()

    if keyword in db[user_id]:
        db[user_id].remove(keyword)

    save_db(db)

    await interaction.response.send_message(
        f"🧹 {interaction.user.mention} removiste **{keyword}**"
    )


@tree.command(name="mysubs", description="Show your subscriptions")
async def mysubs(interaction: discord.Interaction):
    db = load_db()
    subs = db.get(str(interaction.user.id), [])

    await interaction.response.send_message(
        f"📌 Tus palabras clave: {', '.join(subs) if subs else 'ninguna'}",
        ephemeral=True
    )

# ===== DEBUG =====
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    print("📩", message.content)
    await bot.process_commands(message)

# ===== READY =====
@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)
    synced = await tree.sync(guild=guild)
    print(f"Synced {len(synced)} commands")
    print(f"Bot connected as {bot.user}")

# ===== RUN =====
bot.run(os.getenv("DISCORD_TOKEN"))