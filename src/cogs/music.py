import asyncio
import re

import discord
import httpx
from discord.ext import commands

from src.audio_source import AudioSource
from src.audio_streamer import AudioStreamManager
from src.cache_manager import CacheManager
from src.codec_checker import CodecChecker

cache_manager = CacheManager()
audio_stream_manager = AudioStreamManager(cache_manager=cache_manager)
codec_checker = CodecChecker(cache_manager=cache_manager)

url_pattern = r"^(https?://)?(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)$"


async def audio_playing(ctx):
    """Checks that audio is currently playing before continuing."""
    client = ctx.guild.voice_client
    if client and client.channel and client.source:
        return True
    else:
        raise commands.CommandError("Not currently playing any audio.")


async def in_voice_channel(ctx):
    """Checks that the command sender is in the same voice channel as the bot."""
    voice = ctx.author.voice
    bot_voice = ctx.guild.voice_client
    if (
        voice
        and bot_voice
        and voice.channel
        and bot_voice.channel
        and voice.channel == bot_voice.channel
    ):
        return True
    else:
        raise commands.CommandError("You need to be in the channel to do that.")


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = []
        self.now_playing = None

    @commands.hybrid_command(name="join")
    @commands.guild_only()
    async def join(self, ctx):
        """Joins a voice channel"""
        if not ctx.message.author.voice:
            await ctx.send(
                "{} is not connected to a voice channel".format(ctx.message.author.name)
            )
            return
        else:
            channel = ctx.message.author.voice.channel
        await channel.connect()

    @commands.hybrid_command(name="stop")
    @commands.guild_only()
    async def stop(self, ctx):
        """Stops and disconnects the bot from voice"""
        client = ctx.guild.voice_client
        if client and client.channel:
            await ctx.voice_client.disconnect()
            self.queue = []
            self.now_playing = None
        else:
            raise commands.CommandError("Not in a voice channel.")

    @commands.hybrid_command(name="nowplaying", aliases=["np"])
    @commands.guild_only()
    @commands.check(audio_playing)
    async def nowplaying(self, ctx):
        """Displays information about the current song."""
        embed = discord.Embed(color=discord.Color.blurple())
        embed.add_field(
            name=f"Now playing",
            value=f"[{self.now_playing.title}]({self.now_playing.url}) [{ctx.author.mention}]",
        )
        await ctx.send(embed=embed)

    async def _search_yt(self, args):
        params = {"search_query": args}
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.youtube.com/results", params=params
            )
            search_results = re.findall(r"/watch\?v=(.{11})", response.text)
            return search_results[0]

    @commands.hybrid_command(name="play", aliases=["p"])
    @commands.guild_only()
    async def play(self, ctx, *, song: str):
        """
        Streams from a URL or a search query (supports most sources compatible with yt-dlp).
        """
        try:
            # Defer interaction if it's a slash command
            if ctx.interaction:
                await ctx.interaction.response.defer()

            # Check if the input is a URL; otherwise, search
            if not re.match(url_pattern, song):
                video_id = await self._search_yt(song)
                if not video_id:
                    if ctx.interaction:
                        await ctx.interaction.followup.send(
                            "No video IDs found for the search query."
                        )
                    else:
                        await ctx.send("No video IDs found for the search query.")
                    return
                song = f"https://www.youtube.com/watch?v={video_id}"

            client = ctx.guild.voice_client

            if client and client.channel:
                # Add song to the queue
                source = await AudioSource.from_url(
                    song,
                    audio_stream_manager=audio_stream_manager,
                    codec_checker=codec_checker,
                    loop=self.bot.loop,
                )
                self.queue.append(source)
                embed = discord.Embed(
                    description=f"Queued [{source.title}]({source.url}) [{ctx.author.mention}]",
                    color=discord.Color.blurple(),
                )
                if ctx.interaction:
                    await ctx.interaction.followup.send(embed=embed)
                else:
                    await ctx.send(embed=embed)
            else:
                if ctx.author.voice and ctx.author.voice.channel:
                    # Join the voice channel and play the song
                    channel = ctx.author.voice.channel
                    source = await AudioSource.from_url(
                        song,
                        audio_stream_manager=audio_stream_manager,
                        codec_checker=codec_checker,
                        loop=self.bot.loop,
                    )
                    client = await channel.connect()
                    self._play_song(client, source)
                    embed = discord.Embed(
                        description=f"Now playing [{source.title}]({source.url}) [{ctx.author.mention}]",
                        color=discord.Color.green(),
                    )
                    if ctx.interaction:
                        await ctx.interaction.followup.send(embed=embed)
                    else:
                        await ctx.send(embed=embed)
                else:
                    if ctx.interaction:
                        await ctx.interaction.followup.send(
                            "You are not connected to a voice channel."
                        )
                    else:
                        await ctx.send("You are not connected to a voice channel.")
        except Exception as e:
            if ctx.interaction:
                await ctx.interaction.followup.send(f"An error occurred: {e}")
            else:
                await ctx.send(f"An error occurred: {e}")

    def _play_song(self, client, source):
        self.now_playing = source

        def after_playing(error):
            if error:
                print(f"Error after playing a song: {error}")

            if len(self.queue) > 0:
                next_source = self.queue.pop(0)
                asyncio.run_coroutine_threadsafe(
                    self._play_song(client, next_source), self.bot.loop
                )
            else:
                asyncio.run_coroutine_threadsafe(client.disconnect(), self.bot.loop)

        client.play(source, after=after_playing)

    @commands.hybrid_command(name="queue", aliases=["playlist", "q"])
    @commands.guild_only()
    @commands.check(audio_playing)
    async def queue(self, ctx):
        """Display the current play queue."""
        message = self._queue_text(self.queue)
        embed = discord.Embed(
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Queue", value=message)
        await ctx.send(embed=embed)

    def _queue_text(self, queue):
        """Returns a block of text describing a given song queue."""
        message = []
        if len(queue) > 0:
            for index, song in enumerate(queue):
                message.append(f"{index+1}) {song.title}")
            return "\n".join(message)
        else:
            return "The queue is empty!"

    @commands.hybrid_command(name="clear")
    @commands.guild_only()
    @commands.check(audio_playing)
    async def clear_queue(self, ctx):
        """Clears the play queue without leaving the channel."""
        self.queue = []

    @commands.hybrid_command(name="volume", aliases=["vol", "v"])
    @commands.guild_only()
    @commands.check(audio_playing)
    @commands.check(in_voice_channel)
    async def volume(self, ctx, volume: int):
        """Changes the player's volume"""

        if ctx.voice_client is None:
            return await ctx.send("Not connected to a voice channel.")

        ctx.voice_client.source.volume = volume / 100
        embed = discord.Embed(
            description=f"Changed volume to {volume}% [{ctx.author.mention}]",
            color=discord.Color.blurple(),
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="pause", aliases=["resume"])
    @commands.guild_only()
    @commands.check(audio_playing)
    @commands.check(in_voice_channel)
    async def pause(self, ctx):
        client = ctx.guild.voice_client
        if client.is_paused():
            client.resume()
        else:
            client.pause()

    @commands.hybrid_command(name="skip")
    @commands.guild_only()
    @commands.check(audio_playing)
    @commands.check(in_voice_channel)
    async def skip(self, ctx):
        client = ctx.voice_client
        client.stop()
