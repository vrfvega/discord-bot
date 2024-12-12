import re

import discord
import lavalink
from discord.ext import commands
from lavalink.errors import ClientError
from lavalink.events import QueueEndEvent, TrackStartEvent
from lavalink.server import LoadType

url_rx = re.compile(r"https?://(?:www\.)?.+")


class LavalinkVoiceClient(discord.VoiceProtocol):
    """
    This is the preferred way to handle external voice sending
    This client will be created via a cls in the connect method of the channel
    see the following documentation:
    https://discordpy.readthedocs.io/en/latest/api.html#voiceprotocol
    """

    def __init__(self, client: discord.Client, channel: discord.abc.Connectable):
        self.client = client
        self.channel = channel
        self.guild_id = channel.guild.id
        self._destroyed = False

        if not hasattr(self.client, "lavalink"):
            self.client.lavalink = lavalink.Client(client.user.id)
            self.client.lavalink.add_node(
                host="0.0.0.0",
                port=2333,
                password="youshallnotpass",
                region="us",
                name="default-node",
            )

        # Create a shortcut to the Lavalink client here.
        self.lavalink = self.client.lavalink

    async def on_voice_server_update(self, data):
        # the data needs to be transformed before being handed down to
        # voice_update_handler
        lavalink_data = {"t": "VOICE_SERVER_UPDATE", "d": data}
        await self.lavalink.voice_update_handler(lavalink_data)

    async def on_voice_state_update(self, data):
        channel_id = data["channel_id"]

        if not channel_id:
            await self._destroy()
            return

        self.channel = self.client.get_channel(int(channel_id))

        # the data needs to be transformed before being handed down to
        # voice_update_handler
        lavalink_data = {"t": "VOICE_STATE_UPDATE", "d": data}

        await self.lavalink.voice_update_handler(lavalink_data)

    async def connect(
        self,
        *,
        timeout: float,
        reconnect: bool,
        self_deaf: bool = False,
        self_mute: bool = False,
    ) -> None:
        """
        Connect the bot to the voice channel and create a player_manager
        if it doesn't exist yet.
        """
        # ensure there is a player_manager when creating a new voice_client
        self.lavalink.player_manager.create(guild_id=self.channel.guild.id)
        await self.channel.guild.change_voice_state(
            channel=self.channel, self_mute=self_mute, self_deaf=self_deaf
        )

    async def disconnect(self, *, force: bool = False) -> None:
        """
        Handles the disconnect.
        Cleans up running player and leaves the voice client.
        """
        player = self.lavalink.player_manager.get(self.channel.guild.id)

        # no need to disconnect if we are not connected
        if not force and not player.is_connected:
            return

        # None means disconnect
        await self.channel.guild.change_voice_state(channel=None)

        # update the channel_id of the player to None
        # this must be done because the on_voice_state_update that would set channel_id
        # to None doesn't get dispatched after the disconnect
        player.channel_id = None
        await self._destroy()

    async def _destroy(self):
        self.cleanup()

        if self._destroyed:
            # Idempotency handling, if `disconnect()` is called, the changed voice state
            # could cause this to run a second time.
            return

        self._destroyed = True

        try:
            await self.lavalink.player_manager.destroy(self.guild_id)
        except ClientError:
            pass


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.lavalink: lavalink.Client = bot.lavalink
        self.lavalink.add_event_hooks(self)

    def cog_unload(self):
        """
        This will remove any registered event hooks when the cog is unloaded.
        They will subsequently be registered again once the cog is loaded.

        This effectively allows for event handlers to be updated when the cog is reloaded.
        """
        self.lavalink._event_hooks.clear()

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CommandInvokeError):
            await ctx.send(error.original)
            # The above handles errors thrown in this cog and shows them to the user.
            # This shouldn't be a problem as the only errors thrown in this cog are from `ensure_voice`
            # which contain a reason string, such as "Join a voicechannel" etc. You can modify the above
            # if you want to do things differently.

    async def create_player(ctx: commands.Context):
        """
        A check that is invoked before any commands marked with `@commands.check(create_player)` can run.

        This function will try to create a player for the guild associated with this Context, or raise
        an error which will be relayed to the user if one cannot be created.
        """
        if ctx.guild is None:
            raise commands.NoPrivateMessage()

        player = ctx.bot.lavalink.player_manager.create(ctx.guild.id)
        # Create returns a player if one exists, otherwise creates.
        # This line is important because it ensures that a player always exists for a guild.

        # Most people might consider this a waste of resources for guilds that aren't playing, but this is
        # the easiest and simplest way of ensuring players are created.

        # These are commands that require the bot to join a voicechannel (i.e. initiating playback).
        # Commands such as volume/skip etc don't require the bot to be in a voicechannel so don't need listing here.
        should_connect = ctx.command.name in ("play",)

        voice_client = ctx.voice_client

        if not ctx.author.voice or not ctx.author.voice.channel:
            # Check if we're in a voice channel. If we are, tell the user to join our voice channel.
            if voice_client is not None:
                raise commands.CommandInvokeError(
                    "You need to join my voice channel first."
                )

            # Otherwise, tell them to join any voice channel to begin playing music.
            raise commands.CommandInvokeError("Join a voicechannel first.")

        voice_channel = ctx.author.voice.channel

        if voice_client is None:
            if not should_connect:
                raise commands.CommandInvokeError("I'm not playing music.")

            permissions = voice_channel.permissions_for(ctx.me)

            if not permissions.connect or not permissions.speak:
                raise commands.CommandInvokeError(
                    "I need the `CONNECT` and `SPEAK` permissions."
                )

            if voice_channel.user_limit > 0:
                # A limit of 0 means no limit. Anything higher means that there is a member limit which we need to check.
                # If it's full, and we don't have "move members" permissions, then we cannot join it.
                if (
                    len(voice_channel.members) >= voice_channel.user_limit
                    and not ctx.me.guild_permissions.move_members
                ):
                    raise commands.CommandInvokeError("Your voice channel is full!")

            player.store("channel", ctx.channel.id)
            await ctx.author.voice.channel.connect(cls=LavalinkVoiceClient)
        elif voice_client.channel.id != voice_channel.id:
            raise commands.CommandInvokeError("You need to be in my voicechannel.")

        return True

    @lavalink.listener(TrackStartEvent)
    async def on_track_start(self, event: TrackStartEvent):
        guild_id = event.player.guild_id
        channel_id = event.player.fetch("channel")
        guild = self.bot.get_guild(guild_id)

        if not guild:
            return await self.lavalink.player_manager.destroy(guild_id)

        channel = guild.get_channel(channel_id)

        if channel:
            embed = discord.Embed(color=discord.Color.blurple(), title="Now Playing")
            embed.description = f"[{event.track.title}]({event.track.uri})"
            await channel.send(embed=embed)

    @lavalink.listener(QueueEndEvent)
    async def on_queue_end(self, event: QueueEndEvent):
        guild_id = event.player.guild_id
        guild = self.bot.get_guild(guild_id)

        if guild is not None:
            await guild.voice_client.disconnect(force=True)

    @commands.hybrid_command(aliases=["p"])
    @commands.check(create_player)
    async def play(self, ctx, *, query: str):
        """Searches and plays a song from a given query."""
        # Get the player for this guild from cache.
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        # Remove leading and trailing <>. <> may be used to suppress embedding links in Discord.
        query = query.strip("<>")

        # Check if the user input might be a URL. If it isn't, we can Lavalink do a YouTube search for it instead.
        # SoundCloud searching is possible by prefixing "scsearch:" instead.
        if not url_rx.match(query):
            query = f"ytsearch:{query}"

        # Get the results for the query from Lavalink.
        results = await player.node.get_tracks(query)

        embed = discord.Embed(color=discord.Color.blurple())

        # Valid load_types are:
        #   TRACK    - direct URL to a track
        #   PLAYLIST - direct URL to playlist
        #   SEARCH   - query prefixed with either "ytsearch:" or "scsearch:". This could possibly be expanded with plugins.
        #   EMPTY    - no results for the query (result.tracks will be empty)
        #   ERROR    - the track encountered an exception during loading
        if results.load_type == LoadType.EMPTY:
            embed.title = "Oops..."
            embed.description = "I couldn't find any results for that query."
            return await ctx.send(embed=embed)
        elif results.load_type == LoadType.PLAYLIST:
            tracks = results.tracks

            # Add all of the tracks from the playlist to the queue.
            for track in tracks:
                # requester isn't necessary but it helps keep track of who queued what.
                # You can store additional metadata by passing it as a kwarg (i.e. key=value)
                player.add(track=track, requester=ctx.author.id)

            embed.title = "Playlist Enqueued!"
            embed.description = f"{results.playlist_info.name} - {len(tracks)} tracks"
            return await ctx.send(embed=embed)
        else:
            track = results.tracks[0]

            # requester isn't necessary but it helps keep track of who queued what.
            # You can store additional metadata by passing it as a kwarg (i.e. key=value)
            player.add(track=track, requester=ctx.author.id)

            if player.is_playing:
                embed.title = "Track Enqueued"
                embed.description = f"[{track.title}]({track.uri})"
                return await ctx.send(embed=embed)

        # We don't want to call .play() if the player is playing as that will effectively skip
        # the current track.
        if not player.is_playing:
            await player.play()

    @commands.hybrid_command(aliases=["sk"])
    @commands.check(create_player)
    async def skip(self, ctx):
        """Skips to the next track in the queue."""
        # Get the player for this guild from cache.
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        await player.skip()

    @commands.hybrid_command(aliases=["q"])
    @commands.check(create_player)
    async def queue(self, ctx, page: int = 1):
        """Displays the current queue."""
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        queue = player.queue
        embed = discord.Embed(color=discord.Color.blurple(), title="Queue")

        if not queue:
            embed.description = "The queue is empty."
            return await ctx.send(embed=embed)

        items_per_page = 10
        total_pages = (len(queue) - 1) // items_per_page + 1
        page = max(1, min(page, total_pages))

        start = (page - 1) * items_per_page
        end = start + items_per_page

        embed = discord.Embed(
            color=discord.Color.blurple(),
            title=f"Queue - Page {page}/{total_pages}",
        )

        embed.description = "\n".join(
            f"`{index + 1}.` [{track.title}]({track.uri})"
            for index, track in enumerate(queue[start:end], start=start)
        )
        return await ctx.send(embed=embed)

    @commands.hybrid_command(aliases=["dc"])
    @commands.check(create_player)
    async def disconnect(self, ctx):
        """Disconnects the player from the voice channel and clears its queue."""
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        # The necessary voice channel checks are handled in "create_player."
        # We don't need to duplicate code checking them again.

        # Clear the queue to ensure old tracks don't start playing
        # when someone else queues something.
        player.queue.clear()
        # Stop the current track so Lavalink consumes less resources.
        await player.stop()
        # Disconnect from the voice channel.
        await ctx.voice_client.disconnect(force=True)

        embed = discord.Embed(color=discord.Color.blurple())
        embed.description = (
            "I've automatically left the voice channel due to inactivity."
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Music(bot))
