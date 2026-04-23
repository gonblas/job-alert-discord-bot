import discord
from discord.ext import commands
from discord import app_commands
import os
import re
from supabase import create_client

# ===== CONFIG =====
FORUM_NAME = "jobs-feed"

GUILD_ID = int(os.getenv("GUILD_ID"))
JOBS_CHANNEL_ID = int(os.getenv("JOBS_CHANNEL_ID"))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ===== INTENTS =====
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

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

# ===== DB FUNCTIONS =====

def get_user_subs(user_id):
    res = supabase.table("job_subscriptions") \
        .select("keyword") \
        .eq("user_id", user_id) \
        .execute()

    return [r["keyword"] for r in res.data]


def add_subscription(user_id, keyword):
    try:
        supabase.table("job_subscriptions").insert({
            "user_id": user_id,
            "keyword": keyword
        }).execute()
    except Exception:
        pass


def remove_subscription(user_id, keyword):
    supabase.table("job_subscriptions") \
        .delete() \
        .eq("user_id", user_id) \
        .eq("keyword", keyword) \
        .execute()


def get_all_subscriptions():
    res = supabase.table("job_subscriptions") \
        .select("user_id, keyword") \
        .execute()

    db = {}

    for row in res.data:
        db.setdefault(row["user_id"], []).append(row["keyword"])

    return db


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

        user_subs = get_user_subs(self.user_id)

        if self.keyword in user_subs:
            self.add_item(CancelButton(self.user_id, self.keyword))


class MySubsButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Ver mis suscripciones",
            style=discord.ButtonStyle.secondary
        )

    async def callback(self, interaction: discord.Interaction):
        subs = get_user_subs(str(interaction.user.id))

        if not subs:
            return await interaction.response.send_message(
                "📌 No tenés suscripciones",
                ephemeral=True
            )

        formatted = "\n".join(
            f"{i+1}. {', '.join(sub.split())}"
            for i, sub in enumerate(subs)
        )

        await interaction.response.send_message(
            f"📌 **Tu lista de alertas es:**\n{formatted}",
            ephemeral=True
        )


class CancelButton(discord.ui.Button):
    def __init__(self, user_id, keyword):
        super().__init__(
            label="Eliminar esta alerta",
            style=discord.ButtonStyle.danger
        )
        self.user_id = str(user_id)
        self.keyword = keyword

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message(
                "No podés usar este botón",
                ephemeral=True
            )

        remove_subscription(self.user_id, self.keyword)

        await interaction.response.send_message(
            f"🧹 Eliminaste **{self.keyword}**",
            ephemeral=True
        )


# ===== EVENT =====
@bot.event
async def on_thread_create(thread):
    if not isinstance(thread.parent, discord.ForumChannel):
        return

    if thread.parent.name != FORUM_NAME:
        return

    try:
        starter_message = await thread.fetch_message(thread.id)
        content = starter_message.content.lower()

        db = get_all_subscriptions()

        matches = {}

        for user_id, queries in db.items():
            for query in queries:
                if matches_query(content, query):
                    matches.setdefault(user_id, []).append(query)

        # 🔔 ENVIAR DM EN VEZ DE THREAD PUBLICO
        for user_id, queries in matches.items():
            try:
                user = await bot.fetch_user(int(user_id))

                msg = (
                    "🔔 **Nueva oferta encontrada**\n\n"
                    f"📌 Coincidencias: {', '.join(set(queries))}\n\n"
                    f"🔗 {thread.jump_url}"
                )

                await user.send(msg)

            except Exception as e:
                print(f"Error enviando DM a {user_id}: {e}")

    except Exception as e:
        print("Error:", e)


# ===== COMMANDS =====
@tree.command(name="subscribe", description="Suscribite a alertas de trabajo")
async def subscribe(interaction: discord.Interaction, keyword: str):
    user_id = str(interaction.user.id)
    keyword = keyword.lower()

    add_subscription(user_id, keyword)

    view = SearchView(
        interaction.guild.id,
        JOBS_CHANNEL_ID,
        interaction.user.id,
        keyword
    )

    await interaction.response.send_message(
        f"✅ Suscripto a **{keyword}**",
        view=view,
        ephemeral=True
    )


@tree.command(name="unsubscribe", description="Eliminar una alerta")
async def unsubscribe(interaction: discord.Interaction, index: int):
    subs = get_user_subs(str(interaction.user.id))

    if not subs:
        return await interaction.response.send_message(
            "No tenés suscripciones",
            ephemeral=True
        )

    if index < 1 or index > len(subs):
        return await interaction.response.send_message(
            "Número inválido",
            ephemeral=True
        )

    keyword = subs[index - 1]
    remove_subscription(str(interaction.user.id), keyword)

    await interaction.response.send_message(
        f"🧹 Eliminaste **{keyword}**",
        ephemeral=True
    )


@tree.command(name="mysubs", description="Ver tus suscripciones")
async def mysubs(interaction: discord.Interaction):
    subs = get_user_subs(str(interaction.user.id))

    if not subs:
        return await interaction.response.send_message(
            "📌 No tenés suscripciones",
            ephemeral=True
        )

    formatted = "\n".join(
        f"{i+1}. {', '.join(sub.split())}"
        for i, sub in enumerate(subs)
    )

    await interaction.response.send_message(
        f"📌 **Tus alertas:**\n{formatted}",
        ephemeral=True
    )


# ===== READY =====
@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)
    tree.copy_global_to(guild=guild)
    await tree.sync(guild=guild)

    print(f"Bot conectado como {bot.user}")


# ===== RUN =====
bot.run(os.getenv("DISCORD_TOKEN"))