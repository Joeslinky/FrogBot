import asyncio

async def on_thread_create(thread):
    try:
        await asyncio.sleep(1)
        if thread.parent_id == 1162100167110053888:
            emojis_to_add = ["🐞", "📜", "📹"]
        elif thread.parent_id in [1167651506560962581, 1160318669839147259]:
            emojis_to_add = ["💡", "🧠"]
        else:
            emojis_to_add = []
        first_message = None
        async for message in thread.history(limit=1):
            first_message = message
            break
        if first_message:
            for emoji in emojis_to_add:
                try:
                    await first_message.add_reaction(emoji)
                    await asyncio.sleep(0.5)
                except Exception as e:
                    print(f"Error adding reaction {emoji}: {e}")
                    await asyncio.sleep(2)
    except Exception as e:
        print(f"Error in on_thread_create: {e}")

def setup(client):
    client.event(on_thread_create)
