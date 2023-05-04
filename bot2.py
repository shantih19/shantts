import discord
import os
import math
import sqlite3
from google.cloud import texttospeech
import re
import logging
import asyncio
from io import BytesIO
import flag
import traceback

token = os.getenv("DISC_TOKEN")

logger = logging.getLogger("shanTTS")
logger.setLevel(logging.INFO)
handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")


class OpusAudio(discord.AudioSource):
    def __init__(self, stream):
        self._packer_iter = discord.oggparse.OggStream(stream).iter_packets()

    def read(self):
        return next(self._packer_iter, b"")

    def is_opus(self):
        return True


class Bot(discord.Client):
    messages = asyncio.Queue()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def setup_hook(self):
        self.bg_task = self.loop.create_task(self.queue_handler())

    async def on_ready(self):
        logger.info("Logged on as {0}!".format(self.user))

    async def join_channel(self, channel):
        if not self.client:
            self.client = texttospeech.TextToSpeechAsyncClient()
        if all(i.channel.id != channel.id for i in self.voice_clients):
            await channel.connect()

    async def synthesize(self, message, is_file):
        try:
            mess = re.sub(r"\$|\[(.*?)\]", "", message.content)
            if is_file:
                mess = mess[5:]
            if arg := re.search("\[([a-z]{2}(_|-)[A-Z]{2})\]", message.content):
                lg = re.sub(r"\[|\]", "", arg[0])
                logger.info(lg)

            else:
                lg = "it_IT"
            synthesis_input = (
                texttospeech.SynthesisInput(ssml=mess)
                if mess.startswith("<speak>")
                else texttospeech.SynthesisInput(text=mess)
            )
            for i in message.author.roles:
                if re.match("[sS]he\/[hH]er", i.name):
                    gender = texttospeech.SsmlVoiceGender.FEMALE
                    break
                elif re.match("[hH]e\/[hH]im", i.name):
                    gender = texttospeech.SsmlVoiceGender.MALE
                    break
                else:
                    gender = texttospeech.SsmlVoiceGender.NEUTRAL
            voice = texttospeech.VoiceSelectionParams(
                language_code=lg, ssml_gender=gender
            )
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.OGG_OPUS,
            )
            logger.info("Sending request")
            response = await self.client.synthesize_speech(
                input=synthesis_input, voice=voice, audio_config=audio_config
            )
            logger.info("Got response")
            if not is_file:
                audio = BytesIO(response.audio_content)
                source = OpusAudio(audio)
                await self.join_channel(message.author.voice.channel)
                for i in self.voice_clients:
                    if i.channel.id == message.author.voice.channel.id:
                        i.play(source)
                        break
            else:
                audio_file = discord.File(
                    BytesIO(response.audio_content), "{0}.ogg".format(mess)
                )
                await message.reply(file=audio_file)

        except discord.ClientException as error:
            logger.error(error)
            await message.channel.send(error)

        except Exception as error:
            logger.error(traceback.format_exc())
            logger.error(error)
            await message.channel.send(error)

    async def queue_handler(self):
        await self.wait_until_ready()
        logger.info("Task loaded")
        while not self.is_closed():
            message = self.messages.get()
            for client in self.voice_clients:
                if (
                    client.channel.id == message[0].author.voice.channel.id
                    and client.is_playing()
                ):
                    await asyncio.sleep(1)
            await self.synthesize(*message)
            self.messages.task_done()

    async def on_message(self, message):
        if message.content.startswith("$$leave"):
            await self.voice_clients[0].disconnect()

        elif message.content.startswith("$$cbt"):
            await self.join_channel(message.author.voice.channel)
            try:
                source = discord.FFmpegOpusAudio("cbt.ogg", bitrate=96)
                for client in self.voice_clients:
                    if (
                        client.channel.id == message.author.voice.channel.id
                        and not client.is_playing()
                    ):
                        client.play(source)
            except discord.ClientException as error:
                await message.channel.send(error)

        elif message.content.startswith("$$help"):
            with open("help.txt", "r") as hlp:
                await message.reply(hlp.read())

        elif message.content.startswith("$$languages"):
            response = await self.client.list_voices()
            voices = str(response.voices)
            languages = ""
            lang = re.findall(r'"[a-z]{2}-[A-Z]{2}"', voices)
            for i in lang:
                l = re.sub(r'"', "", i)
                if l not in languages:
                    languages += f"{l} :{l[3:5]}: "
            languages += ""
            await message.reply(flag.flagize(languages))

        elif message.content.startswith("$$stop"):
            for i in self.voice_clients:
                if i.channel.id == message.author.voice.channel.id and i.is_playing():
                    i.stop()
        elif message.content.startswith("$$file"):
            item = (message, True)
            self.messages.put(item)

        elif message.content.startswith("$$amogus"):
            await self.join_channel(message.author.voice.channel)
            try:
                source = discord.FFmpegOpusAudio("amogus.opus", bitrate=96)
                for i in self.voice_clients:
                    if (
                        i.channel.id == message.author.voice.channel.id
                        and not i.is_playing()
                    ):
                        i.play(source)
            except discord.ClientException as error:
                await message.channel.send(error)

        elif message.content.startswith("$$restart"):
            os.system("systemctl restart shantts")

        elif message.content.startswith("$$volume"):
            pass

        elif message.content.startswith("$"):
            item = (message, False)
            self.messages.put(item)

    async def on_voice_state_update(self, member, before, after):
        vc = [
            client for client in self.voice_clients if client.channel == before.channel
        ]
        if not vc:
            return
        vc = vc.pop()
        if (
            vc and after.channel != before.channel and len(vc.channel.members) < 2
        ):  # Member disconnected from channel and bot is alone
            vc.disconnect()

    def set_volume(self, volume):
        if volume <= 0:
            volume = 0.001
        v = 20 * math.log(volume / 100)
        self.volume = min(max(-96, v), 10)

    def get_volume(self):
        v = 100 * math.exp(self.volume / 20)


intents = discord.Intents.default()
intents.message_content = True
bot = Bot(intents=intents)
bot.run(token, log_handler=handler)
