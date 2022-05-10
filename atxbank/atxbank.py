import asyncio
import discord
import requests
import json
import calendar
import logging
import random
import time
from collections import defaultdict, deque, namedtuple
from enum import Enum
from math import ceil
from typing import cast, Iterable, Union, Literal
from numerize import numerize
from datetime import datetime, timedelta

from redbot.cogs.bank import is_owner_if_bank_global
from redbot.cogs.mod.converters import RawUserIds
from redbot.core import Config, bank, commands, errors, checks
from redbot.core.commands.converter import TimedeltaConverter
from redbot.core.bot import Red
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils import AsyncIter
from redbot.core.utils.chat_formatting import box, humanize_number
from redbot.core.utils.menus import close_menu, menu, DEFAULT_CONTROLS

from discord.utils import get
from disputils import BotEmbedPaginator, BotConfirmation, BotMultipleChoice

class AtaraxyBank(commands.Cog):
    """This is a bank extension module for Ataraxy Bank."""
    def __init__(self):
        self.config = Config.get_conf(self,identifier=8284624611696967781,force_registration=True)
        defaults_guild = {
            "work_min":0,
            "work_max":0,
            "work_cooldown_hrs":24,
            "draw_required_role":0,
            "draw_payout":0,
            "draw_announcement":0,
            "booster_role_id":0,
            "voter_role_id":0
        }

        defaults_member = {
            "work_lastused":0
        }

        self.config.register_guild(**defaults_guild)
        self.config.register_member(**defaults_member)

    @commands.group(name="atxbankset")
    async def atxbankset(self,ctx):
        """Config settings for Ataraxy Bank."""

    @atxbankset.command()
    @commands.is_owner()
    async def reset(self,ctx):
        """Reset global variables to default."""

        await self.config.guild(ctx.guild).work_min.set(0)
        await self.config.guild(ctx.guild).work_max.set(0)
        await self.config.guild(ctx.guild).work_cooldown_hrs.set(24)
        await self.config.guild(ctx.guild).draw_payout.set(0)
        await self.config.guild(ctx.guild).draw_announcement.set(0)

        embed = discord.Embed(ctx=ctx,description=f"Global variables reset to default.")
        await ctx.send(embed=embed)

    @atxbankset.command()
    @commands.is_owner()
    async def workpayout(self,ctx,minval=0,maxval=0):
        """Set the min/max currency earned through working. If no values are set, passes through as 0."""

        if minval > maxval:
            embed = discord.Embed(ctx=ctx,description=f"Min cannot be more than max.")
            return await ctx.send(embed=embed)

        else:
            currency = await bank.get_currency_name(ctx.guild)
            await self.config.guild(ctx.guild).work_min.set(minval)
            await self.config.guild(ctx.guild).work_max.set(maxval)

            embed = discord.Embed(ctx=ctx,description=f"Work payout set to: {minval} {currency} - {maxval} {currency}.")
            return await ctx.send(embed=embed)

    @atxbankset.command()
    @commands.is_owner()
    async def workcooldown(self,ctx,cooldown=24):
        """Set the work cooldown (in hours). If no values are set, passes through as 24."""

        await self.config.guild(ctx.guild).work_cooldown_hrs.set(cooldown)

        embed = discord.Embed(ctx=ctx,description=f"Work cooldown set to {cooldown} hours.")
        return await ctx.send(embed=embed)

    @atxbankset.command()
    @commands.is_owner()
    async def drawrequiredrole(self,ctx,roleid=0):
        """Set payout for draws. If no values are set, passes through as 0."""

        await self.config.guild(ctx.guild).draw_required_role.set(roleid)

        embed = discord.Embed(ctx=ctx,description=f"Required role for draw set to <@&{roleid}>.")
        return await ctx.send(embed=embed)

    @atxbankset.command()
    @commands.is_owner()
    async def drawpayout(self,ctx,payout=0):
        """Set payout for draws. If no values are set, passes through as 0."""

        currency = await bank.get_currency_name(ctx.guild)

        await self.config.guild(ctx.guild).draw_payout.set(payout)

        embed = discord.Embed(ctx=ctx,description=f"Draw payout set to {payout} {currency}.")
        return await ctx.send(embed=embed)

    @atxbankset.command()
    @commands.is_owner()
    async def drawannouncement(self,ctx,channelid=0):
        """Set the channel ID for Draw Announcements."""

        await self.config.guild(ctx.guild).draw_announcement.set(channelid)

        embed = discord.Embed(ctx=ctx,description=f"Announcement channel ID set to <#{channelid}>.")
        return await ctx.send(embed=embed)  

    @atxbankset.command()
    @commands.is_owner()
    async def voterrole(self,ctx,roleid=0):
        """Set the role ID for Voters."""

        await self.config.guild(ctx.guild).voter_role_id.set(roleid)

        embed = discord.Embed(ctx=ctx,description=f"Voter role set to <@{roleid}>.")
        return await ctx.send(embed=embed)

    @atxbankset.command()
    @commands.is_owner()
    async def boosterrole(self,ctx,roleid=0):
        """Set the role ID for Server Boosters"""

        await self.config.guild(ctx.guild).booster_role_id.set(roleid)

        embed = discord.Embed(ctx=ctx,description=f"Booster role set to <@{roleid}>.")
        return await ctx.send(embed=embed)

    @commands.command(aliases=["banklb"])
    @commands.guild_only()
    async def bankleaderboard(self, ctx: commands.Context, top: int = 10):
        """Print the leaderboard.

        Defaults to top 10.

        Examples:
            - `[p]leaderboard`
            - `[p]leaderboard 50` - Shows the top 50 instead of top 10.

        **Arguments**

        - `<top>` How many positions on the leaderboard to show. Defaults to 10 if omitted.
        """
        
        show_global = False
        guild = ctx.guild
        author = ctx.author
        embed_requested = await ctx.embed_requested()
        footer_message = "Page {page_num}/{page_len}."
        max_bal = await bank.get_max_balance(ctx.guild)

        if top < 1:
            top = 10

        base_embed = discord.Embed(title="Economy Leaderboard")
        if await bank.is_global() and show_global:
            # show_global is only applicable if bank is global
            bank_sorted = await bank.get_leaderboard(positions=top, guild=None)
            base_embed.set_author(name=ctx.bot.user.name, icon_url=ctx.bot.user.avatar_url)
        else:
            bank_sorted = await bank.get_leaderboard(positions=top, guild=guild)
            if guild:
                base_embed.set_author(name=guild.name, icon_url=guild.icon_url)

        try:
            bal_len = len(humanize_number(bank_sorted[0][1]["balance"]))
            bal_len_max = len(humanize_number(max_bal))
            if bal_len > bal_len_max:
                bal_len = bal_len_max
            # first user is the largest we'll see
        except IndexError:
            return await ctx.send("There are no accounts in the bank.")
        pound_len = len(str(len(bank_sorted)))
        header = "{pound:{pound_len}}{score:{bal_len}}{name:2}\n".format(
            pound="#",
            name="Name",
            score="Wealth",
            bal_len=bal_len + 6,
            pound_len=pound_len + 3,
        )
        highscores = []
        pos = 1
        temp_msg = header
        for acc in bank_sorted:
            try:
                name = guild.get_member(acc[0]).display_name
            except AttributeError:
                user_id = ""
                if await ctx.bot.is_owner(ctx.author):
                    user_id = f"({str(acc[0])})"
                name = f"{acc[1]['name']} {user_id}"

            balance = acc[1]["balance"]
            if balance > max_bal:
                balance = max_bal
                await bank.set_balance(MOCK_MEMBER(acc[0], guild), balance)
            balance = humanize_number(balance)
            if acc[0] != author.id:
                temp_msg += (
                    f"{f'{humanize_number(pos)}.': <{pound_len+2}} "
                    f"{balance: <{bal_len + 5}} {name}\n"
                )

            else:
                temp_msg += (
                    f"{f'{humanize_number(pos)}.': <{pound_len+2}} "
                    f"{balance: <{bal_len + 5}} "
                    f"<<{author.display_name}>>\n"
                )
            if pos % 10 == 0:
                if embed_requested:
                    embed = base_embed.copy()
                    embed.description = box(temp_msg, lang="md")
                    embed.set_footer(
                        text=footer_message.format(
                            page_num=len(highscores) + 1,
                            page_len=ceil(len(bank_sorted) / 10),
                        )
                    )
                    highscores.append(embed)
                else:
                    highscores.append(box(temp_msg, lang="md"))
                temp_msg = header
            pos += 1

        if temp_msg != header:
            if embed_requested:
                embed = base_embed.copy()
                embed.description = box(temp_msg, lang="md")
                embed.set_footer(
                    text=footer_message.format(
                        page_num=len(highscores) + 1,
                        page_len=ceil(len(bank_sorted) / 10),
                    )
                )
                highscores.append(embed)
            else:
                highscores.append(box(temp_msg, lang="md"))

        if highscores:
            await menu(
                ctx,
                highscores,
                DEFAULT_CONTROLS if len(highscores) > 1 else {"\N{CROSS MARK}": close_menu},
            )
        else:
            await ctx.send("No balances found.")

    @commands.command()
    @commands.guild_only()
    async def work(self, ctx: commands.Context):
        """Work for some free monies!

        You get more monies for voting and boosting the server."""
        author = ctx.author
        guild = ctx.guild
        cur_time = time.time()
        allow_work = False

        work_cooldown = await self.config.guild(ctx.guild).work_cooldown_hrs()
        last_work = await self.config.member(author).work_lastused()

        if last_work == 0 or isinstance(last_work,str):
            allow_work = True
        else:
            next_work = last_work + (work_cooldown * 3600) #convert hours to ms

            if cur_time >= next_work:
                allow_work = True
            else:
                dtime_seconds = next_work - cur_time
                waittime = ''

                dtime_days,dtime_seconds = divmod(dtime_seconds,86400)
                dtime_hours,dtime_seconds = divmod(dtime_seconds,3600)
                dtime_minutes,dtime_seconds = divmod(dtime_seconds,60)

                if dtime_days > 0:
                    waittime += f"{int(dtime_days)} days "
                if dtime_hours > 0:
                    waittime += f"{int(dtime_hours)} hours "
                if dtime_minutes > 0:
                    waittime += f"{int(dtime_minutes)} mins "

                embed = discord.Embed(
                    description=f"{author.mention} you have to wait {waittime}before you can work again.",
                    color=(await ctx.embed_colour())
                    )

                await ctx.send(embed=embed)

        if allow_work:

            await self.config.member(author).work_lastused.set(cur_time)

            work_payout_min = await self.config.guild(ctx.guild).work_min()
            work_payout_max = await self.config.guild(ctx.guild).work_max()
            boosterrole = await self.config.guild(ctx.guild).booster_role_id()
            voterrole = await self.config.guild(ctx.guild).voter_role_id()

            currency = await bank.get_currency_name(ctx.guild)
            max_bal = await bank.get_max_balance(ctx.guild)
            current_balance = await bank.get_balance(author)

            is_booster = False
            is_voter = False
            is_level40 = False
            is_level50 = False
            is_level70 = False #802523620194779179
            is_level100 = False #802523775219662859

            if boosterrole != 0 or voterrole != 0:
                for role in author.roles:
                    if role.id == boosterrole:
                        is_booster = True
                    #add voter logic TBD
                    if role.id == voterrole:
                        is_voter = True
                    #Level 40
                    if role.id == 717286702355316758:
                        is_level40 = True
                    #Level 50
                    if role.id == 802523066918764544:
                        is_level50 = True
                    if role.id == 802523620194779179:
                        is_level70 = True
                    if role.id == 802523775219662859:
                        is_level100 = True

            work_payout = random.randint(work_payout_min,work_payout_max)
           
            work_payout_bonus = 0
            work_payout_final = work_payout
            roll = random.randint(0,10)

            #if voted, extra 25
            if is_voter:
                work_payout_final += 25
            #if booster, receive extra 50
            if is_booster:
                work_payout_final += 50
            #if roll 10, receive double
            if roll == 10:
                bonusmult = random.randint(1,10)/10
                work_payout_bonus = round(work_payout_final * bonusmult)
                work_payout_final += int(work_payout_bonus)

            if (current_balance + work_payout_final) > max_bal:
                try:
                    await bank.set_balance(author, max_bal)
                except:
                    pass

            else:
                try:
                    await bank.deposit_credits(author,work_payout_final)
                except:
                    pass

            new_bal = await bank.get_balance(author)

            if roll == 10:
                workmsg = f"Congratulations {author.mention}, you've earned a bonus - your payouts today are increased!\n**You now have {new_bal} {currency}.**"
            else:
                workmsg = f"{author.mention}, you've earned some money!\n**You now have {new_bal} {currency}.**"

            earn_msg = f"\n> Regular Pay: {work_payout} {currency}"

            if roll == 10:
                earn_msg += f"\n> Special Bonus: {int(work_payout_bonus)} {currency}"
            if is_voter:
                earn_msg += f"\n> Voter Bonus: 25 {currency}"
            if is_booster:
                earn_msg += f"\n> Booster Bonus: 50 {currency}"

            embed = discord.Embed(description=workmsg+"\n"+earn_msg+f"\n**Your Total Payout: {work_payout_final} {currency}**",color=(await ctx.embed_colour()))

            await ctx.send(embed=embed)

    @commands.command(aliases=["bal"])
    @commands.guild_only()
    async def balance(self, ctx: commands.Context,user:discord.Member = None):
        """Check your Bank balance"""
        if not user:
            user = ctx.author        

        bal = await bank.get_balance(user)
        currency = await bank.get_currency_name(ctx.guild)
        max_bal = await bank.get_max_balance(ctx.guild)

        cur_time = time.time()
        work_cooldown = await self.config.guild(ctx.guild).work_cooldown_hrs()
        last_work = await self.config.member(user).work_lastused()
        waittime = ""

        if last_work != 0 or not isinstance(last_work,str):
            next_work = last_work + (work_cooldown * 3600)
            dtime_seconds = next_work - cur_time
            dtime_days,dtime_seconds = divmod(dtime_seconds,86400)
            dtime_hours,dtime_seconds = divmod(dtime_seconds,3600)
            dtime_minutes,dtime_seconds = divmod(dtime_seconds,60)

            if dtime_days > 0:
                waittime += f"{int(dtime_days)} days "
            if dtime_hours > 0:
                waittime += f"{int(dtime_hours)} hours "
            if dtime_minutes > 0:
                waittime += f"{int(dtime_minutes)} mins "
    
        if waittime == "":
            work_msg = "You can work for some quick cash! Use the `;work` command."
        else:
            work_msg = f"You can work again in {waittime}."

        if bal > max_bal:
            bal = max_bal
            await bank.set_balance(user, bal)

        lb_pos = await bank.get_leaderboard_position(user)

        if user == ctx.author:
            embed = discord.Embed(
                description=f"**You have {humanize_number(bal)} {currency}.**\nYou are currently #{lb_pos} on the leaderboard.",
                color=(await ctx.embed_colour())
                )
            embed.set_author(name=f"{user.display_name}#{user.discriminator}",icon_url=user.avatar_url)
            embed.set_footer(text=work_msg)            
        else:
            embed = discord.Embed(
                description=f"**{user.display_name} has {humanize_number(bal)} {currency}.**\nThey are currently #{lb_pos} on the leaderboard.",
                color=(await ctx.embed_colour())
                )
            embed.set_author(name=f"{user.display_name}#{user.discriminator}",icon_url=user.avatar_url)
            embed.set_footer(text=f"Balance report requested by: {ctx.author.display_name}#{ctx.author.discriminator}")
        await ctx.send(embed=embed)
    
    @commands.group(name="bankadmin")
    async def bankadmin(self,ctx):
        """Admin management commands."""

    @checks.is_owner()
    @bankadmin.command()
    @commands.guild_only()
    async def ataraxytaxes(self, ctx):
        """Custom command to apply taxes in Ataraxy."""

        currency = await bank.get_currency_name(ctx.guild)
        max_bal = await bank.get_max_balance(ctx.guild)

        for user in ctx.guild.members:
            if not user.bot:
                
                try:
                    current_balance = await bank.get_balance(user)
                except:
                    current_balance = 0

                if current_balance > 0:

                    if current_balance > 10000:
                        tax_amount = int(current_balance * 0.30)
                    elif current_balance > 8000:
                        tax_amount = int(current_balance * 0.15)
                    elif current_balance > 5000:
                        tax_amount = int(current_balance * 0.10)
                    elif current_balance > 3000:
                        tax_amount = int(current_balance * 0.05)
                    elif current_balance > 1000:
                        tax_amount = int(current_balance * 0.02)
                    else:
                        tax_amount = 0

                    if (current_balance - tax_amount) < 0:
                        try:
                            await bank.set_balance(user, 0)
                        except:
                            await ctx.send(f"Error handling taxes for {user}. \nc.bal {current_balance} \nt.amt {tax_amount}")
                    else:
                        try:
                            await bank.withdraw_credits(user, tax_amount)
                        except:
                            await ctx.send(f"Error handling taxes for {user}.")

    @checks.is_owner()
    @bankadmin.command()
    @commands.guild_only()
    async def prune(self, ctx, confirmation: bool = False):
        """Prunes all bank accounts. If run as a global bank, prunes all accounts. Otherwise, only prunes those in the current server."""

        global_bank = await bank.is_global()

        if confirmation is False:
            await ctx.send(
                _(
                    "This will delete all bank accounts for users no longer recognized by Ataraxy."
                    "\nIf you're sure, type "
                    "`{prefix}admin prune yes`"
                ).format(prefix=ctx.clean_prefix)
            )

        else:
            if global_bank is True:
                await bank.bank_prune(self.bot)
                await ctx.send(
                    _(
                        "Bank accounts for users who "
                        "no longer share a server with the bot have been pruned."
                    )
                )

            if global_bank is False:
                await bank.bank_prune(self.bot, guild=ctx.guild)
                await ctx.send(
                    _("Bank accounts for users no longer in this server have been deleted.")
                )

    @checks.is_owner()
    @commands.command()
    @commands.guild_only()
    async def bankdraw(self, ctx, confirmation: bool = False):
        """ Give a a pre-set amount of economy to a random user in the guild/role."""

        draw_payout = await self.config.guild(ctx.guild).draw_payout()
        draw_announcement = await self.config.guild(ctx.guild).draw_announcement()
        server_booster_role = await self.config.guild(ctx.guild).booster_role_id()
        draw_eligible_role = await self.config.guild(ctx.guild).draw_required_role()
        
        currency_name = await bank.get_currency_name(ctx.guild)
        target_channel = discord.utils.get(ctx.guild.channels,id=draw_announcement)

        booster_perks = True
        eligible_members = []
        draw_list = []

        #get Mee6 Level 10 role
        try:
            draw_eligible_role = ctx.guild.get_role(draw_eligible_role)
            draw_members = draw_eligible_role.members
        except:
            draw_members = ctx.guild.members

        try:
            server_booster_role = ctx.guild.get_role(server_booster_role)
        except:
            server_booster_role = None
            booster_perks = False

        #Admin role
        #required_role = ctx.guild.get_role(753994711999578133)

        for member in draw_members:
            if not member.bot and member is not ctx.guild.owner:
                eligible_members.append(member)
                draw_list.append(member)

                for role in member.roles:
                    #Lv20
                    if role.id == 717286501146427403:
                        draw_list.append(member)
                    #Lv30
                    if role.id == 717286636060409867:
                        draw_list.append(member)
                    #Lv40
                    if role.id == 717286702355316758:
                        draw_list.append(member)
                    #Lv50
                    if role.id == 802523066918764544:
                        draw_list.append(member)

        if len(eligible_members) > 1:
            random.shuffle(draw_list)
            winner = random.choice(draw_list)
            winning_message = f"Congratulations {winner.mention}, you've won today's draw of **{draw_payout} {currency_name}**!"
            bonus_nitro = False
            bonus_l70 = False
            bonus_l100 = False

            #check for nitro bonus
            for role in winner.roles:
                if booster_perks:
                    if role.id == server_booster_role:
                        bonus_nitro = True
                if role.id == 802523066918764544:
                    bonus_nitro = True
                #L70
                if role.id == 802523620194779179:
                    bonus_l70 =  True
                if role.id == 802523775219662859:
                    bonus_l100 = True

            if bonus_nitro:                
                nitro_chance = random.choice(range(1,11))
                if nitro_chance == 10:
                    winning_message = f"Congratulations {winner.mention}, you've won **1 months' Discord Nitro!** Please DM <@&644530507505336330> to redeem."
                    return await target_channel.send(winning_message)

            if bonus_l70:
                draw_payout = draw_payout * 1.5
                winning_message += f"```Your Lv70 benefits have boosted your winnings to {draw_payout}!```"

            if bonus_l100:
                draw_payout = draw_payout * 2
                winning_message += f"```Your Lv100 benefits have boosted your winnings to {draw_payout}!```"
                
            await bank.deposit_credits(winner, draw_payout)
            await target_channel.send(winning_message)

    @commands.group(name="manageuser")
    async def manageuser(self,ctx):
        """Bulk user management commands. Restricted to Admin users."""

    @checks.admin_or_permissions(manage_guild=True)
    @manageuser.command()
    @commands.guild_only()
    async def addmoney(self, ctx, amount:int, target: discord.Member):
        """Gives money to a user."""

        execute = True

        if not target:
            await ctx.send_help()
            execute = False
            return

        if amount <= 0:
            await ctx.send("Amount must be positive.")
            execute = False

        if execute:

            currency = await bank.get_currency_name(ctx.guild)
            max_bal = await bank.get_max_balance(ctx.guild)

            if target.bot:
                await ctx.send("Cannot give money to bots!")
            if not target.bot:
                try:
                    current_balance = await bank.get_balance(target)

                    if (current_balance + amount) > max_bal:
                        try:
                            await bank.set_balance(target, max_bal)
                        except:
                            pass
                    else:
                        try:
                            await bank.deposit_credits(target,amount)
                        except:
                            pass
                except:
                    pass
        await ctx.tick()

    @checks.admin_or_permissions(manage_guild=True)
    @manageuser.command()
    @commands.guild_only()
    async def removemoney(self, ctx, amount:int, target: discord.Member):
        """Removes money to a user."""

        execute = True

        if not target:
            await ctx.send_help()
            execute = False
            return

        if amount <= 0:
            await ctx.send("Amount must be positive.")
            execute = False

        if execute:

            currency = await bank.get_currency_name(ctx.guild)
            max_bal = await bank.get_max_balance(ctx.guild)

            if target.bot:
                await ctx.send("Cannot remove money from bots!")
            if not target.bot:
                try:
                    current_balance = await bank.get_balance(target)

                    if (current_balance - amount) < 0:
                        try:
                            await bank.set_balance(target, 0)
                        except:
                            pass
                    else:
                        try:
                            await bank.withdraw_credits(target,amount)
                        except:
                            pass
                except:
                    pass
        await ctx.tick()

    @commands.group(name="massmoney")
    async def massmoney(self,ctx):
        """Bulk user management commands. Restricted to Admin users."""

    @checks.admin_or_permissions(manage_guild=True)
    @massmoney.command()
    @commands.guild_only()
    async def percent(self, ctx, percent:float, action, target: discord.Role=None):
        """Apply a percentage increase/decrease to a group of users by role. If a role is not specified, applies to everyone in the server. Does not work on bots.

        Combine this command with the FIFO cog from Fox (https://github.com/bobloy/Fox-V3) to set up recurring behaviour. Multiple runs can be created to apply taxes on multiple roles.

        *action accepts either "income" or "deduction".
        *percentage value must be between 0 and 1."""

        execute = True

        if action not in ["income","deduction"]:
            await ctx.send("Action isn't recognized. Should be *income* or *deduction*.")
            execute = False
        if percent > 1 or percent < 0:
            await ctx.send("Percentage amount is invalid.")
            execute = False

        if execute:

            currency = await bank.get_currency_name(ctx.guild)
            max_bal = await bank.get_max_balance(ctx.guild)

            if target == None:
                ttarget = ctx.guild.members
            else:
                ttarget = target.members

            for user in ttarget:
                if not user.bot:
                    try:
                        current_balance = await bank.get_balance(user)
                        amount_delta = int(current_balance * amount)

                        if action=='deduction':
                            if (current_balance - amount_delta) < 0:
                                try:
                                    await bank.set_balance(user, 0)
                                except:
                                    pass
                            else:
                                try:
                                    await bank.withdraw_credits(user, amount_delta)
                                except:
                                    pass

                        elif action=='income':
                            if (current_balance + amount_delta) > max_bal:
                                try:
                                    await bank.set_balance(user, max_bal)
                                except:
                                    pass
                            else:
                                try:
                                    await bank.deposit_credits(user,amount_delta)
                                except:
                                    pass
                    except:
                        pass
        await ctx.tick()

    @checks.admin_or_permissions(manage_guild=True)
    @massmoney.command()
    @commands.guild_only()
    async def numeric(self, ctx, amount:float, action, target: discord.Role=None):
        """Apply a numeric increase/decrease to a group of users by role. If a role is not specified, applies to everyone in the server. Does not work on bots.

        Combine this command with the FIFO cog from Fox (https://github.com/bobloy/Fox-V3) to set up recurring behaviour. Multiple runs can be created to apply taxes on multiple roles.

        *action accepts either "income" or "deduction". Defaults to income.
        *amount value must be above 0."""

        execute = True

        if action not in ["income","deduction"]:
            await ctx.send("Action isn't recognized. Should be *income* or *deduction*.")
            execute = False
        if amount < 0:
            await ctx.send("Amount is invalid.")
            execute = False

        if execute:

            currency = await bank.get_currency_name(ctx.guild)
            max_bal = await bank.get_max_balance(ctx.guild)
            amount_delta = int(amount)

            if target == None:
                ttarget = ctx.guild.members
            else:
                ttarget = target.members

            for user in ttarget:
                if not user.bot:
                    try:
                        current_balance = await bank.get_balance(user)

                        if action=='deduction':
                            if (current_balance - amount_delta) < 0:
                                try:
                                    await bank.set_balance(user, 0)
                                except:
                                    pass
                            else:
                                try:
                                    await bank.withdraw_credits(user, amount_delta)
                                except:
                                    pass

                        elif action=='income':
                            if (current_balance + amount_delta) > max_bal:
                                try:
                                    await bank.set_balance(user, max_bal)
                                except:
                                    pass
                            else:
                                try:
                                    await bank.deposit_credits(user,amount_delta)
                                except:
                                    pass
                    except:
                        pass
        await ctx.tick()