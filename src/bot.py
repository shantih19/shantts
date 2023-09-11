#!python3
import discord
from commands import Commands
import os
import math
from google.cloud import texttospeech
import re
import logging
import asyncio
import queue
from io import BytesIO
import traceback
from prometheus_client import Gauge, Summary, start_http_server

NAMESPACE = "shantts"

token = os.getenv("DISC_TOKEN")

logging.basicConfig(level=logging.INFO)

start_http_server(port=9901, addr="10.0.0.1")


class OpusAudio(discord.AudioSource):
    def __init__(self, stream: BytesIO):
        self._packer_iter = discord.oggparse.OggStream(stream).iter_packets()

    def read(self):
        return next(self._packer_iter, b"")

    def is_opus(self):
        return True


class Bot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def setup_hook(self):
        self.bg_task = self.loop.create_task(self.queue_handler())
        self.client = texttospeech.TextToSpeechAsyncClient()
        self.queue_gauge = Gauge(
            "queue_size", "Size of queue for synthesis", namespace=NAMESPACE
        )
        self.request_time = Summary(
            "request_time", "Time of execution for a request", namespace=NAMESPACE
        )
        self.request_size = Summary(
            "request_size", "Size of request", namespace=NAMESPACE
        )
        self.queue_gauge.set(0)
        self.commands = Commands(self)
        self.messages = queue.Queue()
        self.volume = {}

    async def on_ready(self):
        logging.info("Logged on as {0}!".format(self.user))

    async def join_channel(self, member: discord.Member):
        if member.voice and member.voice.channel:
            channel = member.voice.channel
            if all(client.channel.id != channel.id for client in self.voice_clients):
                await channel.connect()
                self.volume[channel.id] = 100
            return True
        return False

    async def synthesize(self, message: discord.Message, is_file: bool):
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
                volume_gain_db=volume_db(
                    self.volume.get(message.author.voice.channel.id, 100)
                ),
            )
            logging.info("Sending TTS request")

            if is_file or await self.join_channel(message.author):
                response = await self.client.synthesize_speech(
                    input=synthesis_input, voice=voice, audio_config=audio_config
                )
                self.request_size.observe(len(message.content))
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
            self.queue_gauge.dec()
            logging.debug(f"extracted {message} from queue")
            for client in self.voice_clients:
                if (
                    client.channel.id == message[0].author.voice.channel.id
                    and client.is_playing()
                ):
                    await asyncio.sleep(1)
            await self.synthesize(*message)

    async def command_not_found(self):
        pass

    async def on_message(self, message: discord.Message):
        with self.request_time.time():
            if message.content.startswith("$$"):
                command = message.content[2:]
                logging.info(command)
                logging.debug(self.commands.commands)
                if command in self.commands.commands:
                    await getattr(self.commands, command, self.command_not_found)(
                        message
                    )

            elif message.content.startswith("$"):
                item = (message, False)
                self.messages.put_nowait(item)
                self.queue_gauge.inc()

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
