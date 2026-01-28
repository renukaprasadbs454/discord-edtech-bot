"""
Admin Cog for Discord Mind Matrix Bot
Provides administrative commands for managing students and verification
"""

import discord
from discord import app_commands
from discord.ext import commands
import logging
import csv
import io
from datetime import datetime
from typing import Optional

import config
from database import db

logger = logging.getLogger("admin")


class Admin(commands.Cog):
    """Administrative commands for bot management"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    # ============================================
    # PERMISSION CHECK
    # ============================================
    def is_admin():
        """Check if user has admin permissions"""
        async def predicate(interaction: discord.Interaction) -> bool:
            return interaction.user.guild_permissions.administrator
        return app_commands.check(predicate)
    
    # ============================================
    # STATS COMMAND
    # ============================================
    @app_commands.command(name="stats", description="View verification statistics")
    @app_commands.default_permissions(administrator=True)
    async def stats(self, interaction: discord.Interaction):
        """Show verification statistics"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            stats = await db.get_verification_stats()
            
            embed = discord.Embed(
                title="📊 Verification Statistics",
                color=config.EMBED_COLOR,
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(
                name="👥 Total Students",
                value=f"```{stats['total_students']:,}```",
                inline=True
            )
            embed.add_field(
                name="✅ Verified",
                value=f"```{stats['verified']:,}```",
                inline=True
            )
            embed.add_field(
                name="⏳ Unverified",
                value=f"```{stats['unverified']:,}```",
                inline=True
            )
            embed.add_field(
                name="📨 Pending OTPs",
                value=f"```{stats['pending_otps']:,}```",
                inline=True
            )
            
            # Calculate percentage
            if stats['total_students'] > 0:
                percentage = (stats['verified'] / stats['total_students']) * 100
                embed.add_field(
                    name="📈 Verification Rate",
                    value=f"```{percentage:.1f}%```",
                    inline=True
                )
            
            embed.set_footer(text=f"Requested by {interaction.user.name}")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error fetching stats: {e}")
            await interaction.followup.send("❌ Error fetching statistics.", ephemeral=True)
    
    # ============================================
    # MANUAL VERIFY COMMAND
    # ============================================
    @app_commands.command(name="force-verify", description="Manually verify a user (Admin only)")
    @app_commands.describe(
        user="The Discord user to verify",
        email="The registered email address (name, course & batch fetched from database)"
    )
    @app_commands.default_permissions(administrator=True)
    async def force_verify(
        self, 
        interaction: discord.Interaction, 
        user: discord.Member,
        email: str
    ):
        """Manually verify a user without OTP - fetches name, course & batch from database"""
        await interaction.response.defer(ephemeral=True)
        
        email = email.strip().lower()
        
        # Check if student exists in database
        student = await db.get_student_by_email(email)
        
        if not student:
            await interaction.followup.send(
                f"❌ **Email not found in database**\n\n"
                f"The email `{email}` is not registered.\n"
                f"Please add the student first using `/add-student` or import via CSV.",
                ephemeral=True
            )
            return
        
        # Get student info from database (new 5-column format with university)
        student_name = student.get("name", "Unknown")
        university = student.get("university", "")  # University (e.g., "VTU", "GTU")
        course = student.get("course", "")  # Category name (e.g., "Android App Development")
        batch = student.get("batch", "")    # Batch name (e.g., "Nomads")
        
        # Check if email is already verified
        if student.get("is_verified") and student.get("discord_id"):
            existing_id = student.get("discord_id")
            await interaction.followup.send(
                f"⚠️ **Email already verified**\n\n"
                f"This email is linked to Discord ID: `{existing_id}`\n"
                f"Use `/unverify` first if you want to re-assign.",
                ephemeral=True
            )
            return
        
        # Verify the student
        verified = await db.verify_student(email, user.id)
        
        if not verified:
            await interaction.followup.send("❌ This Discord user might already be verified with another email.", ephemeral=True)
            return
        
        # Assign roles (using new 5-column CSV structure with university prefix)
        roles_to_add = []
        role_names = []
        
        # 1. Add Verified role
        if config.VERIFIED_ROLE_ID:
            verified_role = interaction.guild.get_role(config.VERIFIED_ROLE_ID)
            if verified_role:
                roles_to_add.append(verified_role)
                role_names.append(verified_role.name)
        
        # 2. Handle Course role (Category-based) - now with university prefix
        # University = "VTU", Course = "Android App Development" → Role = "VTU-Android App Development Intern"
        if course:
            if university:
                course_role_name = f"{university}-{course} Intern"
            else:
                course_role_name = f"{course} Intern"
            course_role = discord.utils.get(interaction.guild.roles, name=course_role_name)
            if course_role:
                roles_to_add.append(course_role)
                role_names.append(course_role.name)
            else:
                logger.warning(f"Course role '{course_role_name}' not found. Run verification first to auto-create.")
        
        # 3. Handle Batch role - now with university prefix
        # University = "VTU", Batch = "Nomads" → Role = "VTU-Nomads"
        if batch:
            if university:
                batch_role_name = f"{university}-{batch}"
            else:
                batch_role_name = batch
            batch_role = discord.utils.get(interaction.guild.roles, name=batch_role_name)
            if batch_role:
                roles_to_add.append(batch_role)
                role_names.append(batch_role.name)
            else:
                logger.warning(f"Batch role '{batch_role_name}' not found. Run verification first to auto-create.")
        
        try:
            if roles_to_add:
                await user.add_roles(*roles_to_add, reason=f"Force verified by {interaction.user.name}")
        except discord.Forbidden:
            await interaction.followup.send("⚠️ Verified in DB but couldn't assign roles (missing permissions).", ephemeral=True)
            return
        
        await db.log_verification_action(email, user.id, "FORCE_VERIFY", "SUCCESS", f"By admin: {interaction.user.name}")
        
        embed = discord.Embed(
            title="✅ User Force Verified",
            color=config.SUCCESS_COLOR
        )
        embed.add_field(name="User", value=user.mention, inline=True)
        embed.add_field(name="Name", value=student_name, inline=True)
        embed.add_field(name="Email", value=email, inline=True)
        if university:
            embed.add_field(name="University", value=university, inline=True)
        embed.add_field(name="Course", value=course or "N/A", inline=True)
        if batch:
            embed.add_field(name="Batch", value=batch, inline=True)
        if role_names:
            embed.add_field(name="Roles Assigned", value=", ".join(role_names), inline=False)
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        logger.info(f"Force verified: {user.name} ({user.id}) with email {email} by admin {interaction.user.name}")
    
    # ============================================
    # UNVERIFY COMMAND
    # ============================================
    @app_commands.command(name="unverify", description="Remove verification from a user (Admin only)")
    @app_commands.describe(
        user="The Discord user to unverify",
        email="Or unverify by email address"
    )
    @app_commands.default_permissions(administrator=True)
    async def unverify(
        self, 
        interaction: discord.Interaction, 
        user: Optional[discord.Member] = None,
        email: Optional[str] = None
    ):
        """Remove verification from a user and ALL related roles"""
        await interaction.response.defer(ephemeral=True)
        
        # Must provide at least one option
        if not user and not email:
            await interaction.followup.send("❌ Please provide either a **user** or **email**.", ephemeral=True)
            return
        
        # Get student data
        student = None
        if user:
            student = await db.get_student_by_discord_id(user.id)
        elif email:
            email = email.strip().lower()
            student = await db.get_student_by_email(email)
        
        if not student:
            await interaction.followup.send("❌ No verified record found.", ephemeral=True)
            return
        
        if not student.get("is_verified") or not student.get("discord_id"):
            await interaction.followup.send("❌ This student is not currently verified.", ephemeral=True)
            return
        
        # Get the Discord member if we only have email
        discord_id = student.get("discord_id")
        if not user:
            user = interaction.guild.get_member(discord_id)
            if not user:
                # User left the server but still in DB - just clear DB
                await db.unverify_student(discord_id)
                await interaction.followup.send(
                    f"✅ **Database cleared**\n\nEmail `{student.get('email')}` unverified.\n"
                    f"(User not in server, no roles to remove)",
                    ephemeral=True
                )
                return
        
        # Get the student's university, course and batch to identify which roles to remove
        university = student.get("university", "")  # University
        course = student.get("course", "")  # Category name
        batch = student.get("batch", "")    # Batch name
        
        # Remove from database
        await db.unverify_student(user.id)
        
        # Remove ALL related roles
        roles_to_remove = []
        
        # 1. Remove Verified role
        if config.VERIFIED_ROLE_ID:
            verified_role = interaction.guild.get_role(config.VERIFIED_ROLE_ID)
            if verified_role and verified_role in user.roles:
                roles_to_remove.append(verified_role)
        
        # 2. Remove legacy course roles from config.COURSE_ROLE_MAPPING
        for course_name, role_id in config.COURSE_ROLE_MAPPING.items():
            course_role = interaction.guild.get_role(role_id)
            if course_role and course_role in user.roles:
                roles_to_remove.append(course_role)
        
        # 3. Remove Course Intern role (new 5-column format with university prefix)
        # University = "VTU", Course = "Android App Development" → Role = "VTU-Android App Development Intern"
        if course:
            if university:
                course_role_name = f"{university}-{course} Intern"
            else:
                course_role_name = f"{course} Intern"
            course_role = discord.utils.get(interaction.guild.roles, name=course_role_name)
            if course_role and course_role in user.roles:
                roles_to_remove.append(course_role)
        
        # 4. Remove Batch role (new 5-column format with university prefix)
        # University = "VTU", Batch = "Nomads" → Role = "VTU-Nomads"
        if batch:
            if university:
                batch_role_name = f"{university}-{batch}"
            else:
                batch_role_name = batch
            batch_role = discord.utils.get(interaction.guild.roles, name=batch_role_name)
            if batch_role and batch_role in user.roles:
                roles_to_remove.append(batch_role)
        
        removed_role_names = [r.name for r in roles_to_remove]
        
        try:
            if roles_to_remove:
                await user.remove_roles(*roles_to_remove, reason=f"Unverified by {interaction.user.name}")
        except discord.Forbidden:
            pass
        
        await db.log_verification_action(student.get("email"), user.id, "UNVERIFY", "SUCCESS", f"By admin: {interaction.user.name}, Roles removed: {removed_role_names}")
        
        embed = discord.Embed(
            title="🚫 User Unverified",
            description=f"{user.mention} has been unverified.",
            color=config.WARNING_COLOR
        )
        embed.add_field(name="Email", value=student.get("email", "N/A"), inline=True)
        if university:
            embed.add_field(name="University", value=university, inline=True)
        if course:
            embed.add_field(name="Course", value=course, inline=True)
        if batch:
            embed.add_field(name="Batch", value=batch, inline=True)
        if removed_role_names:
            embed.add_field(name="Roles Removed", value=", ".join(removed_role_names), inline=False)
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.info(f"Unverified: {user.name} ({user.id}) by admin {interaction.user.name}. Roles removed: {removed_role_names}")
    
    # ============================================
    # LOOKUP COMMAND
    # ============================================
    @app_commands.command(name="lookup", description="Look up a user's verification status (Admin only)")
    @app_commands.describe(
        user="The Discord user to look up",
        email="Or look up by email address"
    )
    @app_commands.default_permissions(administrator=True)
    async def lookup(
        self, 
        interaction: discord.Interaction, 
        user: Optional[discord.Member] = None,
        email: Optional[str] = None
    ):
        """Look up verification status"""
        await interaction.response.defer(ephemeral=True)
        
        if not user and not email:
            await interaction.followup.send("❌ Please provide either a user or email.", ephemeral=True)
            return
        
        student = None
        if user:
            student = await db.get_student_by_discord_id(user.id)
        elif email:
            student = await db.get_student_by_email(email.strip().lower())
        
        if not student:
            await interaction.followup.send("❌ No record found.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🔍 Student Record",
            color=config.EMBED_COLOR
        )
        embed.add_field(name="Name", value=student.get("name", "N/A"), inline=True)
        embed.add_field(name="Email", value=student.get("email", "N/A"), inline=True)
        
        # Show university if available (new 5-column format)
        university = student.get("university", "")
        if university:
            embed.add_field(name="University", value=university, inline=True)
        
        embed.add_field(name="Course", value=student.get("course", "N/A"), inline=True)
        
        # Show batch if available (new 5-column format)
        batch = student.get("batch", "")
        if batch:
            embed.add_field(name="Batch", value=batch, inline=True)
        
        embed.add_field(name="Verified", value="✅ Yes" if student.get("is_verified") else "❌ No", inline=True)
        
        if student.get("discord_id"):
            embed.add_field(name="Discord ID", value=student.get("discord_id"), inline=True)
        if student.get("verified_at"):
            embed.add_field(name="Verified At", value=student.get("verified_at").strftime("%Y-%m-%d %H:%M UTC"), inline=True)
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    # ============================================
    # ADD STUDENT COMMAND
    # ============================================
    @app_commands.command(name="add-student", description="Add a single student to the database (Admin only)")
    @app_commands.describe(
        email="Student's email address",
        name="Student's name",
        university="University code (e.g., 'VTU' or 'GTU')",
        course="Course/Category name (e.g., 'Android App Development')",
        batch="Batch name (e.g., 'Nomads')"
    )
    @app_commands.default_permissions(administrator=True)
    async def add_student(
        self, 
        interaction: discord.Interaction, 
        email: str,
        name: str,
        university: str,
        course: str,
        batch: Optional[str] = None
    ):
        """Add a student to the database"""
        await interaction.response.defer(ephemeral=True)
        
        success = await db.add_student(
            email.strip().lower(), 
            name.strip(), 
            course.strip(),
            batch.strip() if batch else "",
            university.strip().upper()
        )
        
        if success:
            embed = discord.Embed(
                title="✅ Student Added",
                color=config.SUCCESS_COLOR
            )
            embed.add_field(name="Email", value=email, inline=True)
            embed.add_field(name="Name", value=name, inline=True)
            embed.add_field(name="University", value=university.upper(), inline=True)
            embed.add_field(name="Course", value=course, inline=True)
            if batch:
                embed.add_field(name="Batch", value=batch, inline=True)
        else:
            embed = discord.Embed(
                title="❌ Failed to Add",
                description="Student with this email already exists.",
                color=config.ERROR_COLOR
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    # ============================================
    # BROADCAST COMMAND
    # ============================================
    @app_commands.command(name="broadcast", description="Send a message to all verified students (Admin only)")
    @app_commands.describe(
        message="The message to broadcast",
        course="Target specific course (optional)"
    )
    @app_commands.default_permissions(administrator=True)
    async def broadcast(
        self, 
        interaction: discord.Interaction, 
        message: str,
        course: Optional[str] = None
    ):
        """Broadcast a message to verified students"""
        await interaction.response.defer(ephemeral=True)
        
        # Get target role
        target_role = None
        if course and course in config.COURSE_ROLE_MAPPING:
            target_role = interaction.guild.get_role(config.COURSE_ROLE_MAPPING[course])
        elif config.VERIFIED_ROLE_ID:
            target_role = interaction.guild.get_role(config.VERIFIED_ROLE_ID)
        
        if not target_role:
            await interaction.followup.send("❌ Could not find target role.", ephemeral=True)
            return
        
        # Create broadcast embed
        embed = discord.Embed(
            title="📢 Announcement",
            description=message,
            color=config.EMBED_COLOR,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"From: {interaction.user.name}")
        
        # Send to a channel (you might want to specify which channel)
        # For now, send to the current channel
        await interaction.channel.send(
            content=f"{target_role.mention}",
            embed=embed
        )
        
        await interaction.followup.send(f"✅ Broadcast sent to {target_role.name}!", ephemeral=True)


async def setup(bot: commands.Bot):
    """Setup function to add the cog to the bot"""
    await bot.add_cog(Admin(bot))
