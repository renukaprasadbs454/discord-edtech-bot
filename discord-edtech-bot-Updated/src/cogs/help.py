"""
Help Cog for Discord Mind Matrix Bot
Provides custom help command with detailed information
"""

import discord
from discord import app_commands
from discord.ext import commands
import config


class HelpView(discord.ui.View):
    """Interactive help menu with buttons"""
    
    def __init__(self):
        super().__init__(timeout=180)  # 3 minute timeout
    
    @discord.ui.button(label="Verification", style=discord.ButtonStyle.primary, emoji="🔐")
    async def verification_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🔐 Verification Commands",
            description="Commands to verify your student status",
            color=config.EMBED_COLOR
        )
        embed.add_field(
            name="/verify",
            value="Start the verification process\n`/verify email:your@email.com`",
            inline=False
        )
        embed.add_field(
            name="/otp",
            value="Enter your OTP code\n`/otp code:123456`",
            inline=False
        )
        embed.add_field(
            name="/reverify",
            value="Request a new OTP code if the previous one expired",
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="FAQ", style=discord.ButtonStyle.secondary, emoji="❓")
    async def faq_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="❓ Frequently Asked Questions",
            color=config.EMBED_COLOR
        )
        embed.add_field(
            name="I didn't receive the OTP email?",
            value="• Check your spam/junk folder\n• Wait 60 seconds and use `/reverify`\n• Contact support if it still doesn't work",
            inline=False
        )
        embed.add_field(
            name="My email is not found?",
            value="Make sure you're using the email you registered with. Contact support if you believe this is an error.",
            inline=False
        )
        embed.add_field(
            name="I entered the wrong OTP?",
            value="You have 3 attempts. After that, wait 60 seconds and request a new OTP.",
            inline=False
        )
        embed.add_field(
            name="How do I access course channels?",
            value="After verification, you'll automatically get access to your enrolled course channels.",
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Admin Commands", style=discord.ButtonStyle.danger, emoji="⚙️")
    async def admin_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admin commands are only visible to administrators.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="⚙️ Admin Commands",
            description="Commands for server administrators",
            color=config.ERROR_COLOR
        )
        embed.add_field(
            name="/stats",
            value="View verification statistics",
            inline=False
        )
        embed.add_field(
            name="/force-verify",
            value="Manually verify a user\n`/force-verify user:@User email:email@example.com course:Course A`",
            inline=False
        )
        embed.add_field(
            name="/unverify",
            value="Remove verification from a user\n`/unverify user:@User`",
            inline=False
        )
        embed.add_field(
            name="/lookup",
            value="Look up student records\n`/lookup user:@User` or `/lookup email:email@example.com`",
            inline=False
        )
        embed.add_field(
            name="/add-student",
            value="Add a student to the database\n`/add-student email:email@example.com name:John Doe course:Course A`",
            inline=False
        )
        embed.add_field(
            name="/broadcast",
            value="Send announcement to verified students\n`/broadcast message:Hello! course:Course A`",
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class Help(commands.Cog):
    """Custom help command"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(name="help", description="Get help with bot commands")
    async def help_command(self, interaction: discord.Interaction):
        """Display the help menu"""
        embed = discord.Embed(
            title="🎓 Mind Matrix Bot Help",
            description="Welcome to the Mind Matrix Discord Bot!\n\nClick the buttons below to learn about different features.",
            color=config.EMBED_COLOR
        )
        
        embed.add_field(
            name="🔐 Getting Started",
            value="1️⃣ Use `/verify email:your@email.com`\n2️⃣ Check your email for the OTP code\n3️⃣ Use `/otp code:XXXXXX` to complete verification",
            inline=False
        )
        
        embed.add_field(
            name="📚 Quick Commands",
            value="`/verify` - Start verification\n`/otp` - Enter OTP code\n`/help` - Show this menu",
            inline=False
        )
        
        embed.set_footer(text="Click a button below for more details")
        
        view = HelpView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Respond to help mentions"""
        if message.author.bot:
            return
        
        # Check if bot is mentioned with "help"
        if self.bot.user in message.mentions and "help" in message.content.lower():
            embed = discord.Embed(
                title="Need Help?",
                description="Use `/help` for the help menu!",
                color=config.EMBED_COLOR
            )
            await message.reply(embed=embed, delete_after=10)


async def setup(bot: commands.Bot):
    """Setup function to add the cog to the bot"""
    await bot.add_cog(Help(bot))
