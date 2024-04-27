# modules.emoji

from disnake import Button, ButtonStyle, ActionRow, Embed, ChannelType
from modules.utils.database import db_access_with_retry, update_points
from modules.roles import check_user_points
from disnake.ui import Button, ActionRow
from datetime import datetime, timedelta
import disnake
import asyncio
import sqlite3

bot_replies = {}

emoji_actions = {
    "✅": "handle_checkmark_reaction",
    "👍": "handle_thumbsup_reaction",
    "👎": "handle_thumbsdown_reaction"
}

emoji_points = {
    "🐞": 250,
    "📜": 250,
    "📹": 500,
    "💡": 100,
    "🧠": 250,
    "❤️": 100
}

emoji_responses = {
    "🐞": "their bug report",
    "📜": "submitting an error log",
    "📹": "including footage",
    "💡": "a feature request",
    "🧠": "making sure it was well-thought-out",
    "❤️": "being a good frog"
}

async def handle_thumbsup_reaction(bot, payload):
    channel = bot.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)
    if message.author != bot.user:
        return
    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    required_rank_id = 1198482895342411846
    if not any(role.id >= required_rank_id for role in member.roles):
        return
    print(f"Thumbs up reaction received from user {payload.user_id}")
    await message.reply("Thank you for your positive feedback!")

async def handle_thumbsdown_reaction(bot, payload):
    channel = bot.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)
    if message.author != bot.user:
        return
    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    required_rank_id = 1198482895342411846
    if not any(role.id >= required_rank_id for role in member.roles):
        return
    print(f"Thumbs down reaction received from user {payload.user_id}")
    await message.reply("We're sorry to hear that. We'll strive to do better.")
    
async def process_close(bot, payload):
    if payload.user_id == bot.user.id:
        return
    if payload.guild_id is None:
        return
    emoji_name = str(payload.emoji)
    if emoji_name not in emoji_actions:
        return
    message = await bot.get_channel(payload.channel_id).fetch_message(payload.message_id)
    if emoji_name == "✅" and ChannelType.forum and (payload.member.guild_permissions.administrator or payload.user_id == 126123710435295232):
        await handle_checkmark_reaction(bot, payload, message.author.id)

conn = sqlite3.connect('reminders.db')
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS reminders (id INTEGER PRIMARY KEY, user_id INTEGER, channel_id INTEGER, message_id INTEGER, reminder_time TEXT)')

create_embed_and_buttons = lambda user_id: (Embed(title="Resolution of Request/Report", description=f"<@{user_id}>, your request or report is considered resolved. Are you satisfied with the resolution?", color=0x3498db).set_footer(text="Selecting 'Yes' will close and delete this thread. Selecting 'No' will keep the thread open."), ActionRow(Button(style=ButtonStyle.success, label="Yes"), Button(style=ButtonStyle.danger, label="No")))

async def send_reminder(bot, user_id, channel_id, message_id, delay): await asyncio.sleep(delay); await bot.get_channel(channel_id).send(f"<@{user_id}>, please select an option.")

async def load_reminders(bot):
    now = datetime.now()
    reminders = c.execute('SELECT user_id, channel_id, message_id, reminder_time FROM reminders').fetchall()
    for user_id, channel_id, message_id, reminder_time in reminders:
        if datetime.fromisoformat(reminder_time) > now:
            channel = bot.get_channel(channel_id)
            if channel is None:
                print(f"Channel with ID {channel_id} not found or bot does not have access.")
                continue
            message = await channel.fetch_message(message_id)
            if message is not None:
                embed, action_row = create_embed_and_buttons(user_id)
                await message.edit(embed=embed, components=[action_row])
            delay = (datetime.fromisoformat(reminder_time) - now).total_seconds()
            asyncio.create_task(send_reminder(bot, user_id, channel_id, message_id, delay))

load_reminders_on_start = lambda bot: bot.loop.create_task(load_reminders(bot))

async def handle_checkmark_reaction(bot, payload, original_poster_id, load_only=False):
    if load_only: return await load_reminders(bot)
    channel = bot.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)
    if message is None:
        return
    thread_id = message.thread.id
    guild = bot.get_guild(payload.guild_id)
    embed, action_row = create_embed_and_buttons(original_poster_id)
    satisfaction_message = await channel.send(embed=embed, components=[action_row])
    check = lambda interaction: isinstance(interaction, disnake.MessageInteraction) and interaction.message.id == satisfaction_message.id and interaction.user.id == original_poster_id
    reminder_time = datetime.now() + timedelta(seconds=43200)
    c.execute('INSERT INTO reminders (user_id, channel_id, message_id, reminder_time) VALUES (?, ?, ?, ?)', (original_poster_id, payload.channel_id, satisfaction_message.id, reminder_time.isoformat()))
    conn.commit()
    reminder_task = asyncio.create_task(send_reminder(bot, original_poster_id, payload.channel_id, satisfaction_message.id, 43200))
    try:
        interaction = await bot.wait_for("interaction", timeout=86400, check=check)
        reminder_task.cancel()
        c.execute('DELETE FROM reminders WHERE user_id = ? AND channel_id = ? AND message_id = ?', (original_poster_id, payload.channel_id, satisfaction_message.id))
        conn.commit()
        await interaction.response.defer()
        if interaction.component.label == "Yes":
            await interaction.edit_original_message(content="Excellent! We're pleased to know you're satisfied. This thread will now be closed.", embed=None, components=[])
            thread = disnake.utils.get(guild.threads, id=thread_id)
            if thread is not None: await thread.delete()
            else: await channel.send(f"No thread found with ID {thread_id}.")
        else: await interaction.edit_original_message(content="We're sorry to hear that. We'll strive to do better.", embed=None, components=[])
    except asyncio.TimeoutError:
        reminder_task.cancel()
        c.execute('DELETE FROM reminders WHERE user_id = ? AND channel_id = ? AND message_id = ?', (original_poster_id, payload.channel_id, satisfaction_message.id))
        conn.commit()
        await channel.send(f"<@{original_poster_id}>, you did not select an option within 24 hours. This thread will now be closed.")
        thread = disnake.utils.get(guild.threads, id=thread_id)
        if thread is not None: await thread.delete()
        else: await channel.send(f"No thread found with ID {thread_id}.")

async def process_emoji_reaction(bot, payload):
    guild = bot.get_guild(payload.guild_id)
    reactor = guild.get_member(payload.user_id)
    if not reactor.guild_permissions.administrator:
        return
    channel = bot.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)
    user_id = message.author.id
    user_points = get_user_points(user_id)
    points_to_add = emoji_points[str(payload.emoji)]
    new_points = user_points + points_to_add
    if await update_points(user_id, new_points):
        await check_user_points(bot)
    await manage_bot_response(bot, payload, points_to_add, str(payload.emoji))

async def process_reaction(bot, payload):
    if payload.guild_id is None:
        return
    emoji_name = str(payload.emoji)
    if emoji_name in emoji_points:
        await process_emoji_reaction(bot, payload)
    elif emoji_name in emoji_actions:
        if emoji_name == "✅":
            await process_close(bot, payload)
        else:
            function_name = emoji_actions[emoji_name]
            function = globals()[function_name]
            await function(bot, payload)

def get_user_points(user_id):
    user_points_dict = db_access_with_retry('SELECT * FROM user_points WHERE user_id = ?', (user_id,))
    return user_points_dict[0][1] if user_points_dict else 0

async def manage_bot_response(bot, payload, points_to_add, emoji_name):
    channel = bot.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)
    bot_reply_info = bot_replies.get(message.id, {'reply_id': None, 'total_points': 0, 'reasons': []})
    if emoji_responses[emoji_name] not in bot_reply_info['reasons']:
        bot_reply_info['reasons'].append(emoji_responses[emoji_name])
    total_points = bot_reply_info['total_points'] + points_to_add
    embed = create_points_embed(message.author, total_points, bot_reply_info['reasons'], emoji_name)
    if bot_reply_info['reply_id']:
        try:
            bot_reply_message = await channel.fetch_message(bot_reply_info['reply_id'])
            await bot_reply_message.edit(embed=embed)
        except disnake.NotFound:
            bot_reply_info['reply_id'] = None
    if not bot_reply_info['reply_id']:
        bot_reply_message = await message.reply(embed=embed)
        bot_reply_info['reply_id'] = bot_reply_message.id
    bot_replies[message.id] = {'reply_id': bot_reply_message.id, 'total_points': total_points, 'reasons': bot_reply_info['reasons']}

def create_points_embed(user, total_points, reasons, emoji_name):
    title = f"Points Updated: {emoji_name}"
    description = f"{user.display_name} was awarded points for:"
    reason_to_emoji = {reason: emoji for emoji, reason in emoji_responses.items()}
    reasons_text = "\n".join([f"{reason_to_emoji.get(reason, '❓')} for {reason}" for reason in reasons])
    embed = disnake.Embed(
        title=title,
        description=description,
        color=disnake.Color.green()
    )
    embed.add_field(name="Reasons", value=reasons_text, inline=False)
    embed.add_field(name="Total Points", value=f"{total_points}", inline=True)
    embed.set_footer(text=f"Updated on {datetime.datetime.now().strftime('%Y-%m-%d')} | '/check_points' for more info.")
    return embed

def setup(client):
    @client.event
    async def on_raw_reaction_add(payload):
        await process_reaction(client, payload)
