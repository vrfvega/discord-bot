import asyncio

import discord
from discord.ext import commands

from src.audio.cache_manager import CacheManager
from src.audio.source import Source
from src.audio.stream_manager import StreamManager
from src.bot.utils.checks import audio_playing
from src.bot.utils.url_utils import URLType, identify_url_type, parse_spotify_url
from src.bot.utils.yt_utils import search_youtube


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = []
        self.now_playing = None
        self.cache_manager = CacheManager()
        self.stream_manager = StreamManager(cache_manager=self.cache_manager)

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

    async def _defer_interaction(self, ctx):
        """Defer the interaction if it's a slash command."""
        if ctx.interaction:
            await ctx.interaction.response.defer()

    async def _send_message(self, ctx, content=None, embed=None):
        """Send a message depending on whether it's a slash command or a text command."""
        if ctx.interaction:
            followup = ctx.interaction.followup
            await followup.send(content=content, embed=embed)
        else:
            await ctx.send(content=content, embed=embed)

    async def _create_audio_source(self, song_url: str):
        """Create an audio source from a URL."""
        source = await Source.from_url(
            song_url,
            audio_stream_manager=self.stream_manager,
            loop=self.bot.loop,
        )
        return source

    async def _add_song_to_queue(self, ctx, song_url: str):
        """Add a song to the queue."""
        source = await self._create_audio_source(song_url)
        self.queue.append(source)
        embed = discord.Embed(
            description=f"Queued [{source.title}]({source.url}) [{ctx.author.mention}]",
            color=discord.Color.blurple(),
        )
        await self._send_message(ctx, embed=embed)

    async def _after_song_played(self, client):
        """Handle the next steps after a song has finished playing."""
        if self.queue:
            next_source = self.queue.pop(0)
            self._play_song(client, next_source)
        else:
            await client.disconnect()

    def _play_song(self, client, source):
        """Play a song and set up the after_playing callback."""
        self.now_playing = source

        def after_playing(error):
            if error:
                print(f"Error after playing a song: {error}")
            client.loop.call_soon_threadsafe(
                asyncio.create_task, self._after_song_played(client)
            )

        client.play(source, after=after_playing)

    @commands.hybrid_command(name="play", aliases=["p"])
    @commands.guild_only()
    async def play(self, ctx, *, song: str):
        """
        Streams from a URL or a search query (supports most sources compatible with yt-dlp).
        """
        try:
            await self._defer_interaction(ctx)

            url_type = identify_url_type(song)

            match url_type:
                case URLType.UNKNOWN:
                    video_id = await search_youtube(song)
                    song = f"https://www.youtube.com/watch?v={video_id}"
                case URLType.SPOTIFY:
                    query = parse_spotify_url(song)
                    video_id = await search_youtube(query)
                    song = f"https://www.youtube.com/watch?v={video_id}"
                case URLType.YOUTUBE:
                    pass

            client = ctx.guild.voice_client

            if client and client.channel:
                await self._add_song_to_queue(ctx, song)
            else:
                if ctx.author.voice and ctx.author.voice.channel:
                    channel = ctx.author.voice.channel
                    source = await self._create_audio_source(song)
                    client = await channel.connect()
                    self._play_song(client, source)
                    embed = discord.Embed(
                        description=f"Now playing [{source.title}]({source.url}) [{ctx.author.mention}]",
                        color=discord.Color.green(),
                    )
                    await self._send_message(ctx, embed=embed)
                else:
                    await self._send_message(
                        ctx, content="You are not connected to a voice channel."
                    )
        except Exception as e:
            await self._send_message(ctx, content=f"An error occurred: {e}")

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
    async def volume(self, ctx, volume: int):
        """Changes the player's volume"""
        ctx.voice_client.source.volume = volume / 100
        embed = discord.Embed(
            description=f"Changed volume to {volume}% [{ctx.author.mention}]",
            color=discord.Color.blurple(),
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="pause", aliases=["resume"])
    @commands.guild_only()
    @commands.check(audio_playing)
    async def pause(self, ctx):
        client = ctx.guild.voice_client
        if client.is_paused():
            client.resume()
        else:
            client.pause()

    @commands.hybrid_command(name="skip")
    @commands.guild_only()
    @commands.check(audio_playing)
    async def skip(self, ctx):
        client = ctx.voice_client
        client.stop()
