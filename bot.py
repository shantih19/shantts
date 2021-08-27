import discord
import os
from gtts import gTTS
import re

token = os.getenv('DISC_TOKEN')
voice = None

print(token)

class Bot(discord.Client):
    async def on_ready(self):
        print("Logged on as {0}!".format(self.user))
    
    async def on_message(self, message):
        global voice
        if message.content.startswith("$join"):
            channel = message.author.voice.channel
            voice = await channel.connect()

        elif message.content.startswith("$leave"):
            await voice.disconnect()

        elif message.content.startswith("$cbt"):
            try:
                source = discord.FFmpegOpusAudio('cbt.ogg', bitrate=96)
                voice.play(source)

            except discord.ClientException as error:
                await message.channel.send(error)

        elif message.content.startswith("$"):
            try:
                mess = re.sub(r'\$|\[(.*?)\]', '', message.content)
                arg = re.search("\[(.*?)\]", message.content)
                if arg:
                    lg = re.sub(r'\[|\]', '', arg.group(0))
                else:
                    lg = 'it'
                print(lg)
                #os.system("pico2wave -w output.wav -l 'it-IT' '" + mess + "'")
                tts = gTTS(mess,lang=lg)
                tts.save('output.mp3')
                source = discord.FFmpegOpusAudio('output.mp3',bitrate=96)
                voice.play(source)

            except discord.ClientException as error:
                await message.channel.send(error)

bot = Bot()
bot.run(token)
