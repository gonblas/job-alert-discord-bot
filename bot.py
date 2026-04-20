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

# ===== DB =====
def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f)

# ===== MATCH =====
def matches(content, keyword):
    return re.search(rf"\b{re.escape(keyword)}\b", content)

# ===== UI (BOTONES) =====
class SearchView(discord.ui.View):
    def __init__(self, guild_id, channel_id):
        super().__init__(timeout=None)

        url = f"https://discord.com/channels/{guild_id}/{channel_id}"

        self.add_item(discord.ui.Button(
            label="🔎 Ver ofertas en jobs-feed",
            style=discord.ButtonStyle.link,
            url=url
        ))

        self.add_item(discord.ui.Button(
            label="📌 Ver mis suscripciones",
            style=discord.ButtonStyle.secondary,
            custom_id="mysubs_button"
        ))

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("❌ Acción cancelada", ephemeral=True)

# ===== EVENT: BOTONES =====
@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        if interaction.data["custom_id"] == "mysubs_button":
            db = load_db()
            subs = db.get(str(interaction.user.id), [])

            await interaction.response.send_message(
                f"📌 Tus keywords: {', '.join(subs) if subs else 'ninguna'}",
                ephemeral=True
            )

# ===== EVENT: NUEVOS POSTS =====
@bot.event
async def on_thread_create(thread):
    print("🔥 THREAD DETECTADO:", thread.parent.name)

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

# ===== SLASH COMMANDS =====
@tree.command(name="subscribe", description="Suscribite a alertas de trabajo")
@app_commands.describe(keyword="Tecnología o rol (ej: python, backend)")
async def subscribe(interaction: discord.Interaction, keyword: str):
    user_id = str(interaction.user.id)
    db = load_db()

    if user_id not in db:
        db[user_id] = []

    keyword = keyword.lower()

    if keyword not in db[user_id]:
        db[user_id].append(keyword)

    save_db(db)

    view = SearchView(interaction.guild.id, JOBS_CHANNEL_ID)

    await interaction.response.send_message(
        f"""✅ {interaction.user.mention} ahora vas a recibir alertas de **{keyword}**

🔔 Las nuevas ofertas que coincidan con tu búsqueda te van a llegar automáticamente.

💡 Para ver las ofertas actuales:
usá el buscador dentro del foro `jobs-feed` filtrando por tu stack.
""",
        view=view
    )

@tree.command(name="unsubscribe", description="Eliminar suscripción")
@app_commands.describe(keyword="Keyword a eliminar")
async def unsubscribe(interaction: discord.Interaction, keyword: str):
    user_id = str(interaction.user.id)
    db = load_db()

    if user_id not in db:
        return await interaction.response.send_message("No tenés suscripciones")

    keyword = keyword.lower()

    if keyword in db[user_id]:
        db[user_id].remove(keyword)

    save_db(db)

    await interaction.response.send_message(
        f"🧹 {interaction.user.mention} eliminó **{keyword}**"
    )

@tree.command(name="mysubs", description="Ver tus suscripciones")
async def mysubs(interaction: discord.Interaction):
    db = load_db()
    subs = db.get(str(interaction.user.id), [])

    await interaction.response.send_message(
        f"📌 Tus keywords: {', '.join(subs) if subs else 'ninguna'}",
        ephemeral=True
    )

# ===== DEBUG MENSAJES =====
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    print("📩", message.content)
    await bot.process_commands(message)

# ===== READY =====
@bot.event
async def on_ready():
    await tree.sync()
    print(f"Bot conectado como {bot.user}")

# ===== RUN =====
bot.run(os.getenv("DISCORD_TOKEN"))