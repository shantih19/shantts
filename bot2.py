import discord
import os
from gtts import gTTS
from google.cloud import texttospeech
import re
import logging
import asyncio
from io import BytesIO

token = os.getenv('DISC_TOKEN')
sound = None
client = texttospeech.TextToSpeechClient()
messages = asyncio.Queue()

logging.basicConfig(level=logging.INFO)

class Bot(discord.Client):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bg_task = self.loop.create_task(self.queue_handler())

    async def on_ready(self):
        logging.info("Logged on as {0}!".format(self.user))
    
    async def synthesize(self, message, is_file):
        global sound
        global messages
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
            synthesis_input = texttospeech.SynthesisInput(text=mess)
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
            audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
            response = client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
            logging.info("Got response")
            logging.info(type(response.audio_content))
            if not is_file:
                with open("output.mp3", "wb") as out:
                    out.write(response.audio_content)
                    source = discord.FFmpegOpusAudio("output.mp3",bitrate=96)
                    sound.play(source)
            else:
                audio_file = discord.File(BytesIO(response.audio_content), "{0}.mp3".format(mess))
                await message.reply(file=audio_file)

        except discord.ClientException as error:
            await message.channel.send(error)

    async def queue_handler(self):
        global messages
        global sound
        await self.wait_until_ready()
        logging.info("Task loaded")
        while not self.is_closed():    
            message = await messages.get()
            logging.info("Got message: {0}".format(message.content))
            while sound.is_playing():
                await asyncio.sleep(0.25)
            await self.synthesize(message, False)
            await asyncio.sleep(0.25)
    
    async def on_message(self, message):
        global sound
        global messages
        if message.content.startswith("$$join"):
            channel = message.author.voice.channel
            sound = await channel.connect()
            logging.info("Connected to voice channel")

        elif message.content.startswith("$$leave"):
            await sound.disconnect()

        elif message.content.startswith("$$cbt"):
            try:
                source = discord.FFmpegOpusAudio('cbt.ogg', bitrate=96)
                sound.play(source)

            except discord.ClientException as error:
                await message.channel.send(error)

        elif message.content.startswith("$$help"):
            with open("help.txt","r") as hlp:
                await message.reply(hlp.read())
        
        elif message.content.startswith("$$languages"):
            voices = str(client.list_voices().voices)
            languages = "```"
            lang = re.findall(r'"[a-z]{2}-[A-Z]{2}"', voices)
            for i in lang:
                l = re.sub(r'"', '', i)
                if l not in languages:
                    languages += l + " "
            languages += "```"
            await message.reply(languages)

        elif message.content.startswith("$$stop"):
            if sound.is_playing():
                sound.stop()

        elif message.content.startswith("$$file"):
            await self.synthesize(message,True)

        elif message.content.startswith("$"):
            await messages.put(message)

bot = Bot()
bot.run(token)
