import discord
import os
import math
import sqlite3
from google.cloud import texttospeech
import re
import logging
import asyncio
import queue
from io import BytesIO
import flag
import traceback
from prometheus_client import Gauge, Summary
from prometheus_async.aio import time, track_inprogress
from prometheus_async.aio.web import start_http_server

NAMESPACE = "shantts"

queue_gauge = Gauge("queue_size", "Size of queue for synthesis", namespace=NAMESPACE)
request_time = Summary(
    "request_time", "Time of execution for a request", namespace=NAMESPACE
)
request_size = Summary("request_size", "Size of request", namespace=NAMESPACE)

token = os.getenv("DISC_TOKEN")

logging.basicConfig(level=logging.DEBUG)

start_http_server(9901, "10.0.0.1")


class OpusAudio(discord.AudioSource):
    def __init__(self, stream):
        self._packer_iter = discord.oggparse.OggStream(stream).iter_packets()

    def read(self):
        return next(self._packer_iter, b"")

    def is_opus(self):
        return True


class Bot(discord.Client):
    messages = queue.Queue()
    queue_gauge.set(0)
    volume = 100

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def setup_hook(self):
        self.bg_task = self.loop.create_task(self.queue_handler())
        self.client = texttospeech.TextToSpeechAsyncClient()

    async def on_ready(self):
        logging.info("Logged on as {0}!".format(self.user))

    async def join_channel(self, member):
        if member.voice and member.voice.channel:
            channel = member.voice.channel
            if all(i.channel.id != channel.id for i in self.voice_clients):
                await channel.connect()
            return True
        return False

    async def synthesize(self, message, is_file):
        try:
            mess = re.sub(r"\$|\[(.*?)\]", "", message.content)
            if is_file:
                mess = mess[5:]
            if arg := re.search("\[([a-z]{2}(_|-)[A-Z]{2})\]", message.content):
                lg = re.sub(r"\[|\]", "", arg[0])

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
                volume_gain_db=volume_db(self.volume),
            )
            logging.info("Sending TTS request")

            if is_file or await self.join_channel(message.author):
                response = await self.client.synthesize_speech(
                    input=synthesis_input, voice=voice, audio_config=audio_config
                )
                request_size.observe(len(message.content))
                logging.info("Got response")
                if not is_file:
                    audio = BytesIO(response.audio_content)
                    source = OpusAudio(audio)
                    if await self.join_channel(message.author):
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
            logging.error(error)
            await message.channel.send(error)

        except Exception as error:
            logging.error(traceback.format_exc())
            logging.error(error)
            await message.channel.send(error)

    async def queue_handler(self):
        await self.wait_until_ready()
        logging.info("Task loaded")
        while not self.is_closed():
            logging.debug("waiting for message..")
            message = None
            while self.messages.empty():
                await asyncio.sleep(1)
            message = self.messages.get_nowait()
            queue_gauge.dec()
            logging.debug(f"extracted {message} from queue")
            for client in self.voice_clients:
                if (
                    client.channel.id == message[0].author.voice.channel.id
                    and client.is_playing()
                ):
                    await asyncio.sleep(1)
            await self.synthesize(*message)

    @time(request_time)
    async def on_message(self, message):
        if message.content.startswith("$$leave"):
            await self.voice_clients[0].disconnect()

        elif message.content.startswith("$$cbt"):
            if await self.join_channel(message.author):
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
            languages = "".join(
                [
                    f"{l[0]} :{l[0].split('-')[1]}:\n"
                    for l in {tuple(voice.language_codes) for voice in response.voices}
                ]
            )
            await message.reply(flag.flagize(languages))

        elif message.content.startswith("$$voices"):
            response = await self.client.list_voices()
            voices = "".join(
                [
                    f"{voice.name} {str(voice.language_codes)}\n"
                    for voice in response.voices
                ]
            ).encode()
            await message.reply(
                "Voices:", file=discord.File(BytesIO(voices), "voices.txt")
            )

        elif message.content.startswith("$$stop"):
            for i in self.voice_clients:
                if i.channel.id == message.author.voice.channel.id and i.is_playing():
                    i.stop()

        elif message.content.startswith("$$file"):
            item = (message, True)
            self.messages.put_nowait(item)
            queue_gauge.inc()

        elif message.content.startswith("$$amogus"):
            if await self.join_channel(message.author):
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
            if vol := "".join(filter(str.isdigit, message.content)):
                self.volume = min(max(0, int(vol)), 150)
            await message.channel.send(f"Current volume: {self.volume}%")

        elif message.content.startswith("$"):
            item = (message, False)
            self.messages.put_nowait(item)
            queue_gauge.inc()

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
            logging.info("Disconnecting for loneliness")
            await vc.disconnect()


def volume_db(volume):
    if volume <= 0:
        volume = 0.001
    v = 5 * math.log(volume / 100)
    logging.debug(f"gain {v} dB")
    return min(max(-96, v), 10)


intents = discord.Intents.default()
intents.message_content = True
bot = Bot(intents=intents)
bot.run(token)
