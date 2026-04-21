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
    return SYNONYMS.get(word, word)

# ===== MATCHING =====
def matches_query(content, query):
    words = query.lower().split()
    normalized_words = [normalize_word(w) for w in words]

    return all(
        re.search(rf"\b{re.escape(word)}\b", content)
        for word in normalized_words
    )

# ===== UI =====
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

        if not subs:
            return await interaction.response.send_message(
                "📌 No tenés suscripciones",
                ephemeral=True
            )

        formatted = "\n".join(
            f"{i+1}. [{', '.join(sub.split())}]"
            for i, sub in enumerate(subs)
        )

        await interaction.response.send_message(
            f"📌 **Tu lista de alertas es:**\n{formatted}",
            ephemeral=True
        )


class CancelButton(discord.ui.Button):
    def __init__(self, user_id, index):
        super().__init__(
            label="Eliminar esta alerta",
            style=discord.ButtonStyle.danger
        )
        self.user_id = str(user_id)
        self.index = index  # index of the subscription

    async def callback(self, interaction: discord.Interaction):
        # Security: only the original user can press the button
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message(
                "No podés usar este botón",
                ephemeral=True
            )

        db = load_db()

        # Check if user has subscriptions
        if self.user_id not in db or not db[self.user_id]:
            return await interaction.response.send_message(
                "No tenés suscripciones",
                ephemeral=True
            )

        subs = db[self.user_id]

        # Validate index (important)
        if self.index < 0 or self.index >= len(subs):
            return await interaction.response.send_message(
                "Esa alerta ya no existe",
                ephemeral=True
            )

        # Remove subscription
        removed = subs.pop(self.index)
        save_db(db)

        # Edit original message (clean UX)
        await interaction.response.edit_message(
            content=f"🧹 Eliminaste **[{', '.join(removed.split())}]**",
            view=None
        )


# ===== EVENT =====
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
            msg += f"\n🔎 Coincidencias: {', '.join(matched)}"
            await thread.send(msg)

    except Exception as e:
        print("Error:", e)

# ===== COMMANDS =====
@tree.command(name="subscribe", description="Suscribite a alertas de trabajo")
@app_commands.describe(keyword="Ej: python junior, js ssr")
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

🔔 Vas a recibir alertas cuando una oferta contenga TODAS esas palabras.

💡 Ejemplo:
`python jr` también matchea con `python junior`

Usá el buscador del foro `jobs-feed` para ver ofertas actuales.
""",
        view=view
    )


@tree.command(name="unsubscribe", description="Eliminar una alerta por número")
@app_commands.describe(index="Número de la alerta (ver con /mysubs)")
async def unsubscribe(interaction: discord.Interaction, index: int):
    await interaction.response.defer(ephemeral=True)

    user_id = str(interaction.user.id)
    db = load_db()

    if user_id not in db or not db[user_id]:
        return await interaction.followup.send(
            "No tenés suscripciones"
        )

    subs = db[user_id]

    if index < 1 or index > len(subs):
        return await interaction.followup.send(
            "Número inválido"
        )

    removed = subs.pop(index - 1)
    save_db(db)

    await interaction.followup.send(
        f"🧹 Eliminaste **[{', '.join(removed.split())}]**"
    )


@tree.command(name="mysubs", description="Ver tus suscripciones")
async def mysubs(interaction: discord.Interaction):
    db = load_db()
    subs = db.get(str(interaction.user.id), [])

    if not subs:
        return await interaction.response.send_message(
            "📌 No tenés suscripciones",
            ephemeral=True
        )

    formatted = "\n".join(
        f"{i+1}. [{', '.join(sub.split())}]"
        for i, sub in enumerate(subs)
    )

    await interaction.response.send_message(
        f"📌 **Tu lista de alertas es:**\n{formatted}\n\n❌ Para eliminar: `/unsubscribe <número>`",
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