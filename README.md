# 🚀 Job Alerts Subscription Bot

This Discord bot was originally built for the **[Paso 1](https://discord.gg/SXUWzw4wj)** Discord community. It provides an automated, personalized job alert system, allowing users to subscribe to specific keywords and receive immediate Direct Messages (DMs) whenever a matching job offer is posted in the community's designated job board.

Instead of users having to manually scroll through hundreds of job postings, the bot quietly monitors the job forum and acts as a personal recruiter, notifying users only when an opportunity matches their specific interests (e.g., "Python", "Junior React").

---

## ✨ Features

* **Keyword Subscriptions:** Users can subscribe to multiple custom keywords or tech stacks.
* **Smart Matching & Synonyms:** Includes a built-in normalizer that translates common abbreviations (e.g., "jr" to "junior", "node" to "nodejs") to ensure users don't miss out on variations of their keywords.
* **Automated DM Notifications:** Scans the content of newly created threads in the Job Forum and sends a private direct message to any user whose subscribed keywords appear in the job description.
* **Interactive UI Views:** Uses Discord UI buttons, allowing users to quickly check their active subscriptions or cancel a specific alert directly from the bot's chat interface.
* **Cloud Database Integration:** Uses Supabase to persistently and securely store user subscriptions.

---

## 🛠️ Commands Overview

| Command | Arguments | Description | Channel Restriction |
| :--- | :--- | :--- | :--- |
| `/subscribe` | `keyword` (String) | Subscribes you to DMs for jobs containing this keyword. | Any channel |
| `/unsubscribe` | `index` (Integer) | Deletes a specific alert based on its number in your list. | Any channel |
| `/mysubs` | *None* | Displays a list of all your active keyword alerts. | Any channel |

---

## ⚙️ How to Host and Modify for Your Server

This bot is highly customizable. If you want to host it on your own server, follow these steps:

### 1. Prerequisites
* **Python 3.8+** installed.
* A Discord Bot Token (created via the [Discord Developer Portal](https://discord.com/developers/applications)).
* A free [Supabase](https://supabase.com/) account for the database.
* The bot must be invited to your server with the `application.commands` scope and the **Message Content** intent enabled. 

### 2. Installation

Clone the repository or download the source code, then install the required Python libraries. Your `requirements.txt` should include `discord.py`, `python-dotenv`, and `supabase`.
```bash
pip install -r requirements.txt
```

### 3. Environment Variables (.env)

Create a .env file in the same directory as your bot script and add the following keys corresponding to your server and Supabase project:

```
DISCORD_TOKEN=your_bot_token_here
GUILD_ID=123456789012345678          # Used to sync commands instantly to your server
JOBS_CHANNEL_ID=123456789012345678   # The ID of your Job Board Forum
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_anon_public_key
```

### 4. Database Setup (Supabase)

Because this bot persistently stores user preferences, you must set up a table in your Supabase project:

1. Go to your Supabase project dashboard -> Table Editor.

2. Create a new table named exactly job_subscriptions.

3. Add the following columns:

  - ``id`` (Type: uuid, Primary Key, Default: uuid_generate_v4())

  - ``user_id`` (Type: text)

  - ``keyword`` (Type: text)

4. Disable RLS (Row Level Security) for simplicity, or configure your policies to allow the bot's service key to insert/delete/select.

### 5. Code Modifications (Constants & Synonyms)

You should tweak a few hardcoded values at the top of the script to match your server's needs:

1. **Target Forum Name:** Change the FORUM_NAME variable (line 9) to exactly match the text name of your job forum channel (e.g., "jobs-feed").

2. **Synonyms Dictionary:** Update the SYNONYMS dictionary (line 26) with abbreviations common in your community to improve the search matching:

  ```python
    # ===== SYNONYMS =====
    SYNONYMS = {
        "jr": "junior",
        "sr": "senior",
        "ssr": "semi senior",
        "node": "nodejs",
        "reactjs": "react",
        # Add your own here!
    }
  ```


### 6. Run the Bot

Start the bot using Python:

```bash
python main.py
```

> **Note:** Because this script uses tree.copy_global_to(guild=guild), the slash commands will sync instantly to the specific Server ID you provided in your .env file, avoiding the usual 1-hour global sync delay.

## Recommended Server Permissions Setup

To get the most out of this bot and ensure it can read the job offers:

1. **Job Forum Channel (``#jobs-feed``):** Ensure the Bot role has the View Channel, Read Message History, and Send Messages in Threads permissions enabled for this specific Forum. If it cannot read the message history, it won't be able to scan the content of new job postings.

2. **User Privacy:** Remind your community that they must have Direct Messages enabled for your server in their privacy settings, otherwise the bot will fail to deliver the job alerts to them.