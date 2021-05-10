import discord
import os
from gtts import gTTS
from google.cloud import texttospeech
import re
import logging
import asyncio
from io import BytesIO
import flag

token = os.getenv('DISC_TOKEN')
client = texttospeech.TextToSpeechAsyncClient()

logging.basicConfig(level=logging.INFO)

class OpusAudio(discord.AudioSource):
    def __init__(self,stream):
        self._packer_iter = discord.oggparse.OggStream(stream).iter_packets()

    def read(self):
        return next(self._packer_iter, b'')

    def is_opus(self):
        return True

class Bot(discord.Client):

    messages = asyncio.Queue()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bg_task = self.loop.create_task(self.queue_handler())

    async def on_ready(self):
        logging.info("Logged on as {0}!".format(self.user))
    
    async def join_channel(self, channel):
        if not self.voice_clients:
            await channel.connect()
        elif not self.voice_clients[0].channel == channel:
            while self.voice_clients[0].is_playing():
                await asyncio.sleep(0.25)
            await self.voice_clients[0].move_to(channel)

    async def synthesize(self, message, is_file):
        try:
            mess = re.sub(r'\$|\[(.*?)\]', '', message.content)
            if is_file:
                mess=mess[5:]
                logging.info(mess)
            arg = re.search("\[([a-z]{2}(_|-)[A-Z]{2})\]", message.content)
            if arg:
                lg = re.sub(r'\[|\]', '', arg.group(0))
                logging.info(lg)
            else:
                lg = 'it_IT'
            synthesis_input = texttospeech.SynthesisInput(text=mess) if not mess.startswith('<speak>') else texttospeech.SynthesisInput(ssml=mess)
            for i in message.author.roles:
                if i.name == "she/her":
                    gender = texttospeech.SsmlVoiceGender.FEMALE
                    break
                elif i.name == "he/him":
                    gender = texttospeech.SsmlVoiceGender.MALE
                    break
                else:
                    gender = texttospeech.SsmlVoiceGender.NEUTRAL
            voice = texttospeech.VoiceSelectionParams(language_code=lg, ssml_gender=gender)
            audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.OGG_OPUS)
            response = await client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
            logging.info("Got response")
            if not is_file:
                await self.join_channel(message.author.voice.channel)
                audio = BytesIO(response.audio_content)
                source = OpusAudio(audio)
                self.voice_clients[0].play(source)
            else:
                audio_file = discord.File(BytesIO(response.audio_content), "{0}.ogg".format(mess))
                await message.reply(file=audio_file)

        except discord.ClientException as error:
            await message.channel.send(error)

    async def queue_handler(self):
        await self.wait_until_ready()
        logging.info("Task loaded")
        while not self.is_closed():
            message = await self.messages.get()
            logging.info("Got message: {0}".format(message.content))
            if self.voice_clients:
                while self.voice_clients[0].is_playing():
                    await asyncio.sleep(0.25)
            await self.synthesize(message, False)
            self.messages.task_done()    

    async def on_message(self, message):
       
        if message.content.startswith("$$leave"):
            await self.voice_clients[0].disconnect()

        elif message.content.startswith("$$cbt"):
            try:
                source = discord.FFmpegOpusAudio('cbt.ogg', bitrate=96)
                self.voice_clients[0].play(source)

            except discord.ClientException as error:
                await message.channel.send(error)

        elif message.content.startswith("$$help"):
            with open("help.txt","r") as hlp:
                await message.reply(hlp.read())
        
        elif message.content.startswith("$$languages"):
            response = await client.list_voices()
            voices = str(response.voices)
            languages = ""
            lang = re.findall(r'"[a-z]{2}-[A-Z]{2}"', voices)
            for i in lang:
                l = re.sub(r'"', '', i)
                if l not in languages:
                    languages += l + " :" + l[3:5]  + ": "
            languages += ""
            await message.reply(flag.flagize(languages))

        elif message.content.startswith("$$stop"):
            if self.voice_clients[0].is_playing():
                self.voice_clients[0].stop()

        elif message.content.startswith("$$file"):
            await self.synthesize(message,True)

        elif message.content.startswith("$"):
            self.messages.put_nowait(message)

bot = Bot()
bot.run(token)
