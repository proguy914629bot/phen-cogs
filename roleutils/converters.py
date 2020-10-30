from typing import Union, Dict
import discord
from unidecode import unidecode
from redbot.core import commands
from rapidfuzz import process
from redbot.core.commands import (
    BadArgument,
    Converter,
    MemberConverter,
    RoleConverter,
    EmojiConverter,
    IDConverter,
)
from redbot.core.utils.chat_formatting import inline

from .utils import is_allowed_by_hierarchy, is_allowed_by_role_hierarchy


# original converter from https://github.com/TrustyJAID/Trusty-cogs/blob/master/serverstats/converters.py#L19
class FuzzyRole(RoleConverter):
    """
    This will accept role ID's, mentions, and perform a fuzzy search for
    roles within the guild and return a list of role objects
    matching partial names

    Guidance code on how to do this from:
    https://github.com/Rapptz/discord.py/blob/rewrite/discord/ext/commands/converter.py#L85
    https://github.com/Cog-Creators/Red-DiscordBot/blob/V3/develop/redbot/cogs/mod/mod.py#L24
    """

    def __init__(self, response: bool = True):
        self.response = response
        super().__init__()

    async def convert(self, ctx: commands.Context, argument: str) -> discord.Role:
        try:
            basic_role = await super().convert(ctx, argument)
        except BadArgument:
            pass
        else:
            return basic_role
        guild = ctx.guild
        result = []
        for r in process.extract(
            argument,
            {r: unidecode(r.name) for r in guild.roles},
            limit=None,
            score_cutoff=75,
        ):
            result.append((r[2], r[1]))

        if not result:
            raise BadArgument(f'Role "{argument}" not found.' if self.response else None)

        sorted_result = sorted(result, key=lambda r: r[1], reverse=True)
        return sorted_result[0][0]


class StrictRole(FuzzyRole):
    def __init__(self, response: bool = True):
        self.response = response
        super().__init__(response)

    async def convert(self, ctx: commands.Context, argument: str) -> discord.Role:
        role = await super().convert(ctx, argument)
        if role.managed:
            raise BadArgument(
                f"`{role}` is an integrated role and cannot be assigned."
                if self.response
                else None
            )
        allowed, message = is_allowed_by_role_hierarchy(ctx.bot, ctx.me, ctx.author, role)
        if not allowed:
            raise BadArgument(message if self.response else None)
        return role


class TouchableMember(MemberConverter):
    def __init__(self, response: bool = True):
        self.response = response
        super().__init__()

    async def convert(self, ctx: commands.Context, argument: str) -> discord.Member:
        member = await super().convert(ctx, argument)
        if not await is_allowed_by_hierarchy(ctx.bot, ctx.author, member):
            raise BadArgument(
                "You cannot do that since you aren't higher than that user in hierarchy."
                if self.response
                else None
            )
        else:
            return member


class RealEmojiConverter(EmojiConverter):
    async def convert(self, ctx: commands.Context, argument: str) -> Union[discord.Emoji, str]:
        try:
            emoji = await super().convert(ctx, argument)
        except BadArgument:
            try:
                await ctx.message.add_reaction(argument)
            except discord.HTTPException:
                raise BadArgument(f'Emoji "{argument}" not found.')
            else:
                emoji = argument
        return emoji


class EmojiRole(StrictRole, RealEmojiConverter):
    async def convert(
        self, ctx: commands.Context, argument: str
    ) -> Dict[discord.Emoji, discord.Role]:
        split = argument.split(";")
        if len(split) < 2:
            raise BadArgument
        emoji = await RealEmojiConverter.convert(self, ctx, split[0])
        role = await StrictRole.convert(self, ctx, split[1])
        return {"emoji": emoji, "role": role}


class ObjectConverter(IDConverter):
    async def convert(self, ctx: commands.Context, argument: str) -> discord.Object:
        match = self._get_id_match(argument)
        if not match:
            raise BadArgument
        return discord.Object(int(match.group(0)))
