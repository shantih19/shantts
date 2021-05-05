import discord
import os
from gtts import gTTS
from google.cloud import texttospeech
import re

token = os.getenv('DISC_TOKEN')
sound = None
client = texttospeech.TextToSpeechClient()

class Bot(discord.Client):
    async def on_ready(self):
        print("Logged on as {0}!".format(self.user))
    
    async def on_message(self, message):
        global sound
        if message.content.startswith("$$join"):
            channel = message.author.voice.channel
            sound = await channel.connect()

        elif message.content.startswith("$$leave"):
            await sound.disconnect()

        elif message.content.startswith("$$cbt"):
            try:
                source = discord.FFmpegOpusAudio('cbt.ogg', bitrate=96)
                sound.play(source)

            except discord.ClientException as error:
                await message.channel.send(error)


        elif message.content.startswith("$"):
            try:
                mess = re.sub(r'\$|\[(.*?)\]', '', message.content)
                arg = re.search("\[(.*?)\]", message.content)
                if arg:
                    lg = re.sub(r'\[|\]', '', arg.group(0))
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
                with open("output.mp3", "wb") as out:
                    out.write(response.audio_content)
                source = discord.FFmpegOpusAudio("output.mp3",bitrate=96)
                sound.play(source)

            except discord.ClientException as error:
                await message.channel.send(error)

bot = Bot()
bot.run(token)
