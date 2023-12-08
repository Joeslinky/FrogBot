# commands/emoji.py
import discord
import sqlite3  # Add this line

async def process_reaction(bot, payload, user_points):
    emoji_points = {
        "🐞": 250,
        "📜": 250,
        "📹": 500,
        "💡": 100,
        "🧠": 250,
        "❤️": 100
    }

    emoji_messages = {
        "🐞": " has been awarded {points} points for their bug report!",
        "📜": " has been awarded {points} points for including an error log in their bug report!",
        "📹": " has been awarded {points} points for including footage in their bug report!",
        "💡": " has been awarded {points} points for their feature request!",
        "🧠": " has been awarded {points} points for their well-thought-out feature request!",
        "❤️": " has been awarded {points} points for being a good frog!"
    }

    emoji_name = str(payload.emoji)
    if emoji_name not in emoji_points:
        return

    guild_id = payload.guild_id
    user_id = payload.user_id

    if user_id is None:
        return

    channel = bot.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)
    author_id = message.author.id

    points_to_add = emoji_points[emoji_name]
    user_points[user_id] = user_points.get(user_id, 0) + points_to_add

    conn = sqlite3.connect('user_points.db')
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO user_points (user_id, points) VALUES (?, ?)', (user_id, user_points[user_id]))
    conn.commit()
    conn.close()

    print(f"Points added: {points_to_add} for {message.author.name} ({message.author.id})")
    message_custom = emoji_messages.get(emoji_name, "")

    if message_custom:
        message_custom_formatted = message_custom.format(points=points_to_add)
        await channel.send(f'{message.author.mention}{message_custom_formatted}')
    else:
        points_formatted = "{:,}".format(user_points[user_id])
        await channel.send(f'{message.author.mention} has been awarded {points_to_add} points! They now have {points_formatted}.')
