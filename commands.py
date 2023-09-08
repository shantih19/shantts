import discord
import flag
from io import BytesIO
import os


class Commands:
    def __init__(self, bot):
        self.bot = bot
        self.commands = [
            method_name
            for method_name in dir(self)
            if not method_name.startswith("__") and callable(getattr(self, method_name))
        ]

    async def leave(self, message: discord.Message):
        await self.bot.leave_channel(message.author)

    async def cbt(self, message: discord.Message):
        if await self.bot.join_channel(message.author):
            try:
                source = discord.FFmpegOpusAudio("cbt.ogg", bitrate=96)
                for client in self.bot.voice_clients:
                    if (
                        client.channel.id == message.author.voice.channel.id
                        and not client.is_playing()
                    ):
                        client.play(source)
            except discord.ClientException as error:
                await message.channel.send(error)

    async def help(self, message: discord.Message):
        with open("help.txt", "r") as hlp:
            await message.reply(hlp.read())

    async def languages(self, message: discord.Message):
        response = await self.bot.client.list_voices()
        languages = "".join(
            [
                f"{l[0]} :{l[0].split('-')[1]}:\n"
                for l in {tuple(voice.language_codes) for voice in response.voices}
            ]
        )
        await message.reply(flag.flagize(languages))

    async def voices(self, message: discord.Message):
        response = await self.bot.client.list_voices()
        voices = "".join(
            [f"{voice.name} {str(voice.language_codes)}\n" for voice in response.voices]
        ).encode()
        await message.reply("Voices:", file=discord.File(BytesIO(voices), "voices.txt"))

    async def stop(self, message: discord.Message):
        for i in self.bot.voice_clients:
            if i.channel.id == message.author.voice.channel.id and i.is_playing():
                i.stop()

    async def file(self, message: discord.Message):
        item = (message, True)
        self.bot.messages.put_nowait(item)
        self.bot.queue_gauge.inc()

    async def amogus(self, message: discord.Message):
        if await self.bot.join_channel(message.author):
            try:
                source = discord.FFmpegOpusAudio("amogus.opus", bitrate=96)
                for client in self.bot.voice_clients:
                    if (
                        client.channel.id == message.author.voice.channel.id
                        and not client.is_playing()
                    ):
                        client.play(source)
            except discord.ClientException as error:
                await message.channel.send(error)

    def restart(self):
        os.system("systemctl restart shantts")

    async def volume(self, message: discord.Message):
        if vol := "".join(filter(str.isdigit, message.content)):
            for client in self.bot.voice_clients:
                if client.channel.id == message.author.voice.channel.id:
                    volume = min(max(0, int(vol)), 150)
                    self.bot.volume[client.channel.id] = volume
                    await message.channel.send(f"Current volume: {volume}%")
