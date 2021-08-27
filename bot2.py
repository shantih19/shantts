import discord
import os
from gtts import gTTS
from google.cloud import texttospeech
import re
import logging
import queue
import asyncio
from io import BytesIO
import flag
import traceback

token = os.getenv('DISC_TOKEN')

logging.basicConfig(level=logging.INFO)

class OpusAudio(discord.AudioSource):
    def __init__(self,stream):
        self._packer_iter = discord.oggparse.OggStream(stream).iter_packets()

    def read(self):
        return next(self._packer_iter, b'')

    def is_opus(self):
        return True

class Bot(discord.Client):


    messages = queue.SimpleQueue()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bg_task = self.loop.create_task(self.queue_handler())

    async def on_ready(self):
        logging.info("Logged on as {0}!".format(self.user))
    
    async def join_channel(self, channel):
        found = False
        for i in self.voice_clients:
            if i.channel.id == channel.id:
                found = True
                break
        if not found:
            await channel.connect()

    async def synthesize(self, message, is_file):
        client = texttospeech.TextToSpeechAsyncClient()
        try:
            mess = re.sub(r'\$|\[(.*?)\]', '', message.content)
            if is_file:
                mess=mess[5:]
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
            logging.info("Sending request")
            response = await client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
            logging.info("Got response")
            if not is_file:
                audio = BytesIO(response.audio_content)
                source = OpusAudio(audio)
                await self.join_channel(message.author.voice.channel)
                for i in self.voice_clients:
                    if i.channel.id == message.author.voice.channel.id:
                        i.play(source)
                        break
            else:
                audio_file = discord.File(BytesIO(response.audio_content), "{0}.ogg".format(mess))
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
            if self.messages.empty():
                await asyncio.sleep(1)
            else:
                message = self.messages.get()
                for i in self.voice_clients:
                    if i.channel.id == message[0].author.voice.channel.id:
                        if i.is_playing():
                            await asyncio.sleep(1)

                await self.synthesize(*message)

    async def on_message(self, message):
       
        if message.content.startswith("$$leave"):

            await self.voice_clients[0].disconnect()

        elif message.content.startswith("$$cbt"):
            await self.join_channel(message.author.voice.channel)
            try:
                source = discord.FFmpegOpusAudio('cbt.ogg', bitrate=96)
                for i in self.voice_clients:
                    if i.channel.id == message.author.voice.channel.id and not i.is_playing():
                        i.play(source)    
            except discord.ClientException as error:
                await message.channel.send(error)

        elif message.content.startswith("$$help"):
            with open("help.txt","r") as hlp:
                await message.reply(hlp.read())
        
        elif message.content.startswith("$$languages"):

            client = texttospeech.TextToSpeechAsyncClient()
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
            for i in self.voice_clients:
                if i.channel.id == message.author.voice.channel.id and i.is_playing():
                    i.stop()
        elif message.content.startswith("$$file"):
            item = (message, True)
            self.messages.put_nowait(item)

        elif message.content.startswith("$$amogus"):
            await self.join_channel(message.author.voice.channel)
            try:
                source = discord.FFmpegOpusAudio("amogus.opus", bitrate=96)
                for i in self.voice_clients:
                    if i.channel.id == message.author.voice.channel.id and not i.is_playing():
                        i.play(source)
            except discord.ClientException as error:
                await message.channel.send(error)

        elif message.content.startswith("$$restart"):
            os.system("systemctl restart shantts")

        elif message.content.startswith("$"):
            item=(message,False)
            self.messages.put_nowait(item)

bot = Bot()
bot.run(token)
