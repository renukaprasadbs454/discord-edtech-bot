"""
Discord Mind Matrix Bot - Main Entry Point
Handles bot initialization and cog loading
"""

import os
import asyncio
import logging
from datetime import datetime

import discord
from discord.ext import commands
from dotenv import load_dotenv

from config import *

# Load environment variables
load_dotenv()

# ============================================
# LOGGING SETUP
# ============================================
# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(f"logs/bot_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("discord_bot")

# ============================================
# BOT CONFIGURATION
# ============================================
# Required Intents for the bot to function
intents = discord.Intents.default()
intents.message_content = True  # Required for reading message content
intents.members = True          # Required for role assignment & member tracking
intents.guilds = True           # Required for server management

# Initialize the bot
bot = commands.Bot(
    command_prefix=config.BOT_PREFIX,
    intents=intents,
    help_command=None  # We'll create a custom help command
)

# ============================================
# EVENTS
# ============================================
@bot.event
async def on_ready():
    """Called when the bot successfully connects to Discord"""
    logger.info(f"Bot logged in as {bot.user.name} (ID: {bot.user.id})")
    logger.info(f"Connected to {len(bot.guilds)} guild(s)")
    
    # Set bot status
    activity = discord.Activity(
        type=discord.ActivityType.watching,
        name="for /verify commands"
    )
    await bot.change_presence(activity=activity)
    
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} slash command(s)")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")
    
    print("=" * 50)
    print(f"✅ Bot is ready!")
    print(f"📌 Logged in as: {bot.user.name}")
    print(f"🆔 Bot ID: {bot.user.id}")
    print(f"🌐 Servers: {len(bot.guilds)}")
    print("=" * 50)


@bot.event
async def on_member_join(member: discord.Member):
    """Called when a new member joins the server"""
    logger.info(f"New member joined: {member.name}#{member.discriminator} (ID: {member.id})")
    
    # Find the verify channel
    verify_channel = member.guild.get_channel(config.VERIFY_CHANNEL_ID)
    
    if verify_channel:
        # Send welcome message (only visible in verify channel)
        try:
            embed = discord.Embed(
                title="Welcome! 🎓",
                description=config.WELCOME_MESSAGE,
                color=config.EMBED_COLOR
            )
            embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
            embed.set_footer(text="Use /verify to get started")
            
            await verify_channel.send(
                content=f"Welcome {member.mention}!",
                embed=embed,
                delete_after=300  # Delete after 5 minutes
            )
        except discord.Forbidden:
            logger.warning(f"Cannot send welcome message - missing permissions")


@bot.event
async def on_command_error(ctx, error):
    """Global error handler for commands"""
    if isinstance(error, commands.CommandNotFound):
        return  # Ignore command not found errors
    
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing required argument: `{error.param.name}`", ephemeral=True)
        return
    
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command.", ephemeral=True)
        return
    
    # Log unexpected errors
    logger.error(f"Command error: {error}", exc_info=True)
    await ctx.send("❌ An unexpected error occurred. Please try again later.", ephemeral=True)


# ============================================
# COG LOADING
# ============================================
async def load_extensions():
    """Load all cogs/extensions"""
    cogs = [
        "src.cogs.verification",
        "src.cogs.admin",
        "src.cogs.help"
    ]
    
    for cog in cogs:
        try:
            await bot.load_extension(cog)
            logger.info(f"Loaded extension: {cog}")
        except Exception as e:
            logger.error(f"Failed to load {cog}: {e}")


# ============================================
# MAIN ENTRY POINT
# ============================================
async def main():
    """Main function to run the bot"""
    async with bot:
        await load_extensions()
        
        token = os.getenv("DISCORD_TOKEN")
        if not token:
            logger.critical("DISCORD_TOKEN not found in environment variables!")
            print("❌ ERROR: Please set DISCORD_TOKEN in your .env file")
            return
        
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
