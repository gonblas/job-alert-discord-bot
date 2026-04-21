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

# ===== MATCHING =====
def matches(content, keyword):
    """Check exact keyword match using regex"""
    return re.search(rf"\b{re.escape(keyword)}\b", content)

# ===== UI COMPONENTS =====
class SearchView(discord.ui.View):
    def __init__(self, guild_id, channel_id, user_id, keyword):
        super().__init__(timeout=120)

        self.user_id = str(user_id)
        self.keyword = keyword.lower()

        url = f"https://discord.com/channels/{guild_id}/{channel_id}"

        # Link button to forum
        self.add_item(discord.ui.Button(
            label="Ver todas las ofertas",
            style=discord.ButtonStyle.link,
            url=url
        ))

        # Button to show user subscriptions
        self.add_item(MySubsButton())

        # Cancel button (unsubscribe behavior)
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
            f"📌 Your keywords: {', '.join(subs) if subs else 'none'}",
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
        # Ensure only the original user can use the button
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message(
                "You cannot use this button",
                ephemeral=True
            )

        db = load_db()

        # Remove keyword like unsubscribe
        if self.user_id in db and self.keyword in db[self.user_id]:
            db[self.user_id].remove(self.keyword)
            save_db(db)

            # Edit original message (better UX)
            await interaction.response.edit_message(
                content=f"🧹 You removed **{self.keyword}** from your subscriptions",
                view=None
            )
        else:
            await interaction.response.send_message(
                "Subscription not found",
                ephemeral=True
            )

# ===== EVENT: NEW THREADS =====
@bot.event
async def on_thread_create(thread):
    print("🔥 THREAD DETECTED:", thread.parent.name)

    # Only process forum threads
    if not isinstance(thread.parent, discord.ForumChannel):
        return

    # Only specific forum
    if thread.parent.name != FORUM_NAME:
        return

    try:
        starter_message = await thread.fetch_message(thread.id)
        content = starter_message.content.lower()

        db = load_db()
        mentions = set()
        matched = set()

        # Match users based on keywords
        for user_id, keywords in db.items():
            for keyword in keywords:
                if matches(content, keyword):
                    mentions.add(f"<@{user_id}>")
                    matched.add(keyword)

        # Notify matched users
        if mentions:
            msg = " ".join(mentions)
            msg += f"\n🔎 Match: {', '.join(matched)}"
            await thread.send(msg)

    except Exception as e:
        print("Error:", e)

# ===== SLASH COMMANDS =====
@tree.command(name="subscribe", description="Subscribe to job alerts")
@app_commands.describe(keyword="Technology or role (e.g. python, backend)")
async def subscribe(interaction: discord.Interaction, keyword: str):
    user_id = str(interaction.user.id)
    db = load_db()

    if user_id not in db:
        db[user_id] = []

    keyword = keyword.lower()

    # Add keyword if not already present
    if keyword not in db[user_id]:
        db[user_id].append(keyword)

    save_db(db)

    # Create UI view with buttons
    view = SearchView(
        interaction.guild.id,
        JOBS_CHANNEL_ID,
        interaction.user.id,
        keyword
    )

    await interaction.response.send_message(
        f"""✅ {interaction.user.mention} you are now subscribed to **{keyword}**

🔔 New matching job posts will be notified automatically.

💡 To browse current offers:
use the search bar inside the `jobs-feed` forum.
""",
        view=view
    )


@tree.command(name="unsubscribe", description="Remove a subscription")
@app_commands.describe(keyword="Keyword to remove")
async def unsubscribe(interaction: discord.Interaction, keyword: str):
    user_id = str(interaction.user.id)
    db = load_db()

    if user_id not in db:
        return await interaction.response.send_message("No subscriptions found")

    keyword = keyword.lower()

    if keyword in db[user_id]:
        db[user_id].remove(keyword)

    save_db(db)

    await interaction.response.send_message(
        f"🧹 {interaction.user.mention} removed **{keyword}**"
    )


@tree.command(name="mysubs", description="Show your subscriptions")
async def mysubs(interaction: discord.Interaction):
    db = load_db()
    subs = db.get(str(interaction.user.id), [])

    await interaction.response.send_message(
        f"📌 Your keywords: {', '.join(subs) if subs else 'none'}",
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