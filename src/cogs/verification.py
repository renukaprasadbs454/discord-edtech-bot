"""
Verification Cog for Discord Mind Matrix Bot
Handles /verify and /otp commands with email OTP verification
Supports automatic Role & Channel creation for University/Course/Batch system

CSV Format (5 columns):
    - Column 1: Name
    - Column 2: Email id
    - Column 3: University (e.g., "VTU" or "GTU")
    - Column 4: Course (becomes Category name, e.g., "Android App Development")
    - Column 5: Batch name (becomes Batch role name, e.g., "Nomads")

Structure created per university:
    VTU - Android App Development (Category)
        #vtu-android-app-development-announcements
        #vtu-android-app-development-discussion
        #vtu-nomads-official (batch-specific)
"""

import os
import re
import random
import string
import logging
import asyncio
import itertools
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import discord
from discord import app_commands
from discord.ext import commands
import aiosmtplib
from dotenv import load_dotenv

import config
from database import db, init_database

load_dotenv()
logger = logging.getLogger("verification")


class Verification(commands.Cog):
    """Cog for handling student email verification"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.otp_cooldowns = {}
        
        # --- EMAIL SWITCHER CONFIG ---
        email_str = os.getenv("SMTP_EMAILS", "")
        pass_str = os.getenv("SMTP_PASSWORDS", "")
        
        self.emails = [e.strip() for e in email_str.split(",") if e.strip()]
        self.passwords = [p.strip() for p in pass_str.split(",") if p.strip()]

        # Optional single-account fallback (only used if SMTP_EMAILS fails)
        self.fallback_email = (os.getenv("SMTP_EMAIL") or "").strip().strip('"').strip("'")
        self.fallback_password = (os.getenv("SMTP_PASSWORD") or "").strip().strip('"').strip("'")
        
        # Persistent counters for the current session
        self.current_email_index = 0  # Which email are we using (0 to 7)
        self.mail_counter = 0         # How many mails sent by CURRENT email
        self.MAX_THRESHOLD = 1900     # Switch after 1900 emails
        
        if self.emails:
            logger.info(f"🚀 Mail Switcher Ready: Starting with {self.emails[0]}")
        else:
            if self.fallback_email:
                logger.warning("⚠️ SMTP_EMAILS not configured — will use SMTP_EMAIL fallback only.")
            else:
                logger.warning("⚠️ No SMTP_EMAILS/SMTP_EMAIL configured — OTP sending will fail until .env is set.")
        
    async def cog_load(self):
        """Called when the cog is loaded - initialize database"""
        await init_database()
        logger.info("Verification cog loaded and database initialized")
    
    # ============================================
    # HELPER: AUTO-CREATE COURSE RESOURCES (Category + Shared Channels)
    # ============================================
    async def ensure_course_resources(self, guild: discord.Guild, university: str, course_name: str) -> tuple[discord.Role, discord.CategoryChannel]:
        """
        Ensures the Course Role and Category with shared channels exist.
        Now includes university prefix for organization.
        
        CSV: university = "VTU", course = "Android App Development"
        Creates (if not exists):
            - Role: "VTU-Android App Development Intern"
            - Category: "VTU - Android App Development"
                - #announcements-vtu-android-app-development (read-only for students)
                - #discussions-vtu-android-app-development (all students can chat)
        
        Returns:
            tuple: (course_role, category) or (None, None) on error
        """
        if not course_name:
            return (None, None)
        
        # Build names with university prefix if provided
        if university:
            course_role_name = f"{university}-{course_name} Intern"
            category_name = f"{university} - {course_name}"
            channel_prefix = f"{university.lower()}-{course_name.lower().replace(' ', '-')}"
        else:
            course_role_name = f"{course_name} Intern"
            category_name = course_name
            channel_prefix = course_name.lower().replace(" ", "-")
        
        # 1. Get or Create COURSE ROLE
        course_role = discord.utils.get(guild.roles, name=course_role_name)
        if not course_role:
            try:
                course_role = await guild.create_role(
                    name=course_role_name,
                    mentionable=True,
                    reason=f"Auto-created by Mind Matrix Bot for {university} - {course_name}" if university else f"Auto-created by Mind Matrix Bot for {course_name}"
                )
                logger.info(f"✅ Created Course Role: {course_role_name}")
            except discord.Forbidden:
                logger.error(f"❌ Missing Permissions: Cannot create role '{course_role_name}'")
                return (None, None)
        
        # 2. Get or Create CATEGORY
        category = discord.utils.get(guild.categories, name=category_name)
        if not category:
            try:
                # Category permissions: Hidden from @everyone, visible to Course Role
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    course_role: discord.PermissionOverwrite(view_channel=True),
                    guild.me: discord.PermissionOverwrite(view_channel=True, manage_channels=True)
                }
                category = await guild.create_category(
                    name=category_name,
                    overwrites=overwrites,
                    reason=f"Auto-created by Mind Matrix Bot for {university} - {course_name}" if university else f"Auto-created by Mind Matrix Bot for {course_name}"
                )
                logger.info(f"✅ Created Category: {category_name}")
            except discord.Forbidden:
                logger.error(f"❌ Missing Permissions: Cannot create category '{category_name}'")
                return (course_role, None)
        
        # 3. Create SHARED CHANNELS inside the Category
        announcement_channel_name = f"announcements-{channel_prefix}"
        discussion_channel_name = f"discussions-{channel_prefix}"
        
        # 3a. Announcements Channel (Students can view, only Admin can send)
        announcement_channel = discord.utils.get(guild.text_channels, name=announcement_channel_name, category=category)
        if not announcement_channel:
            try:
                announcement_overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    course_role: discord.PermissionOverwrite(view_channel=True, send_messages=False),  # Read-only
                    guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
                }
                await guild.create_text_channel(
                    name=announcement_channel_name,
                    category=category,
                    overwrites=announcement_overwrites,
                    topic=f"📢 Official announcements for {university} - {course_name}. Only admins can post." if university else f"📢 Official announcements for {course_name}. Only admins can post."
                )
                logger.info(f"✅ Created Channel: #{announcement_channel_name}")
            except discord.Forbidden:
                logger.error(f"❌ Missing Permissions: Cannot create channel '{announcement_channel_name}'")
        
        # 3b. Discussion Channel (All students can chat)
        discussion_channel = discord.utils.get(guild.text_channels, name=discussion_channel_name, category=category)
        if not discussion_channel:
            try:
                discussion_overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    course_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                    guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
                }
                await guild.create_text_channel(
                    name=discussion_channel_name,
                    category=category,
                    overwrites=discussion_overwrites,
                    topic=f"💬 Discussion forum for all {university} - {course_name} students" if university else f"💬 Discussion forum for all {course_name} students"
                )
                logger.info(f"✅ Created Channel: #{discussion_channel_name}")
            except discord.Forbidden:
                logger.error(f"❌ Missing Permissions: Cannot create channel '{discussion_channel_name}'")
        
        return (course_role, category)
    
    # ============================================
    # HELPER: AUTO-CREATE BATCH RESOURCES (Batch Role + Private Channel)
    # ============================================
    async def ensure_batch_resources(self, guild: discord.Guild, university: str, course_name: str, batch_name: str, category: discord.CategoryChannel) -> discord.Role:
        """
        Ensures the Batch-specific Role and Channel exist.
        Now includes university prefix for organization.
        
        CSV: university = "VTU", course = "Android App Development", batch = "Nomads"
        Creates (if not exists):
            - Role: "VTU-Nomads"
            - Channel: #vtu-nomads-official (inside the Course Category)
        
        Returns:
            discord.Role or None on error
        """
        if not batch_name:
            return None
        
        # Build names with university prefix if provided
        if university:
            batch_role_name = f"{university}-{batch_name}"
            channel_name = f"{university.lower()}-{batch_name.lower().replace(' ', '-')}-official"
        else:
            batch_role_name = batch_name
            channel_name = f"{batch_name.lower().replace(' ', '-')}-official"
        
        # 1. Get or Create BATCH ROLE
        batch_role = discord.utils.get(guild.roles, name=batch_role_name)
        if not batch_role:
            try:
                batch_role = await guild.create_role(
                    name=batch_role_name,
                    mentionable=True,
                    reason=f"Auto-created by Mind Matrix Bot for {university} batch {batch_name}" if university else f"Auto-created by Mind Matrix Bot for batch {batch_name}"
                )
                logger.info(f"✅ Created Batch Role: {batch_role_name}")
            except discord.Forbidden:
                logger.error(f"❌ Missing Permissions: Cannot create role '{batch_role_name}'")
                return None
        
        # 2. Get or Create BATCH-SPECIFIC CHANNEL
        batch_channel = discord.utils.get(guild.text_channels, name=channel_name)
        
        if not batch_channel and category:
            try:
                # Channel visible only to this specific batch
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    batch_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                    guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
                }
                await guild.create_text_channel(
                    name=channel_name,
                    category=category,
                    overwrites=overwrites,
                    topic=f"🔒 Private channel for {university} - {batch_name} batch only" if university else f"🔒 Private channel for {batch_name} batch only"
                )
                logger.info(f"✅ Created Batch Channel: #{channel_name}")
            except discord.Forbidden:
                logger.error(f"❌ Missing Permissions: Cannot create channel '{channel_name}'")
        
        return batch_role
    
    # ============================================
    # UTILITY FUNCTIONS
    # ============================================
    def generate_otp(self, length: int = 6) -> str:
        """Generate a random numeric OTP code"""
        return ''.join(random.choices(string.digits, k=length))
    
    async def send_otp_email(self, email: str, otp: str, name: str = "Student") -> bool:
        """Send OTP preferring SMTP_EMAILS; fallback to SMTP_EMAIL on failure."""
        smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", 587))

        async def _send_with(username: str, password: str) -> None:
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = "🔐 Your Discord Verification Code"
            message["From"] = username
            message["To"] = email

            # Plain text version
            text = f"""
Hello {name},

Your Discord verification code is: {otp}

This code will expire in 5 minutes.

If you did not request this code, please ignore this email.

Best regards,
Mind Matrix Team
            """

            # HTML version
            html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px; }}
        .container {{ max-width: 500px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .otp-code {{ font-size: 36px; font-weight: bold; color: #5865F2; letter-spacing: 8px; text-align: center; padding: 20px; background: #f0f0f0; border-radius: 8px; margin: 20px 0; }}
        .header {{ color: #333; text-align: center; }}
        .footer {{ color: #888; font-size: 12px; text-align: center; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <h2 class="header">🔐 Discord Verification</h2>
        <p>Hello <strong>{name}</strong>,</p>
        <p>Your verification code is:</p>
        <div class="otp-code">{otp}</div>
        <p>This code will expire in <strong>5 minutes</strong>.</p>
        <p>Enter this code using <code>/otp code:{otp}</code> in Discord.</p>
        <div class="footer">
            <p>If you did not request this code, please ignore this email.</p>
        </div>
    </div>
</body>
</html>
            """

            message.attach(MIMEText(text, "plain"))
            message.attach(MIMEText(html, "html"))

            await aiosmtplib.send(
                message,
                hostname=smtp_host,
                port=smtp_port,
                username=username,
                password=password,
                start_tls=True
            )

        list_config_ok = bool(self.emails) and bool(self.passwords) and (len(self.emails) == len(self.passwords))

        # 1) Prefer SMTP_EMAILS (threshold-based)
        if list_config_ok:
            # Check if we need to switch to the next email
            if self.mail_counter >= self.MAX_THRESHOLD:
                self.current_email_index += 1
                self.mail_counter = 0

                if self.current_email_index >= len(self.emails):
                    self.current_email_index = 0

                logger.info(
                    f"🔄 Limit reached! Switching to email #{self.current_email_index + 1}: {self.emails[self.current_email_index]}"
                )

            current_user = self.emails[self.current_email_index]
            current_pass = self.passwords[self.current_email_index]

            try:
                await _send_with(current_user, current_pass)
                self.mail_counter += 1
                logger.info(f"✅ OTP sent to {email} | {current_user} usage: {self.mail_counter}/{self.MAX_THRESHOLD}")
                return True
            except Exception as e:
                logger.error(f"❌ SMTP_EMAILS send failed using {current_user}: {e}")
        else:
            logger.warning("⚠️ SMTP_EMAILS/SMTP_PASSWORDS missing or mismatch — attempting SMTP_EMAIL fallback.")

        # 2) Fallback: SMTP_EMAIL (only if configured)
        if self.fallback_email and self.fallback_password:
            try:
                await _send_with(self.fallback_email, self.fallback_password)
                logger.info(f"✅ OTP sent to {email} | fallback {self.fallback_email}")
                return True
            except Exception as e:
                logger.error(f"❌ Fallback SMTP_EMAIL send failed using {self.fallback_email}: {e}")
                return False

        logger.error("❌ No valid SMTP credentials available (SMTP_EMAILS failed or not set, and SMTP_EMAIL fallback missing).")
        return False
    
    def is_on_cooldown(self, user_id: int) -> tuple[bool, int]:
        """Check if user is on OTP request cooldown"""
        if user_id in self.otp_cooldowns:
            cooldown_end = self.otp_cooldowns[user_id]
            if datetime.utcnow() < cooldown_end:
                remaining = int((cooldown_end - datetime.utcnow()).total_seconds())
                return True, remaining
        return False, 0
    
    def set_cooldown(self, user_id: int):
        """Set OTP request cooldown for user"""
        self.otp_cooldowns[user_id] = datetime.utcnow() + timedelta(seconds=config.OTP_COOLDOWN)
    
    # ============================================
    # SLASH COMMANDS
    # ============================================
    @app_commands.command(name="verify", description="Verify your email to access course channels")
    @app_commands.describe(email="Your registered email address")
    async def verify(self, interaction: discord.Interaction, email: str):
        """
        Start the verification process by sending an OTP to the user's email
        This response is EPHEMERAL - only visible to the user
        """
        await interaction.response.defer(ephemeral=True)  # Ephemeral = private response
        
        user = interaction.user
        email = email.strip().lower()
        
        logger.info(f"Verification attempt: {user.name} ({user.id}) with email {email}")
        
        # Check cooldown
        on_cooldown, remaining = self.is_on_cooldown(user.id)
        if on_cooldown:
            embed = discord.Embed(
                title="⏳ Please Wait",
                description=f"You can request another OTP in **{remaining}** seconds.",
                color=config.WARNING_COLOR
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Check if user is already verified
        existing_student = await db.get_student_by_discord_id(user.id)
        if existing_student and existing_student.get("is_verified"):
            embed = discord.Embed(
                title="✅ Already Verified",
                description="You are already verified! You should have access to your course channels.",
                color=config.SUCCESS_COLOR
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Check if email exists in database
        student = await db.get_student_by_email(email)
        if not student:
            embed = discord.Embed(
                title="❌ Email Not Found",
                description=config.EMAIL_NOT_FOUND,
                color=config.ERROR_COLOR
            )
            await db.log_verification_action(email, user.id, "VERIFY_REQUEST", "FAILED", "Email not in database")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Check if email is already linked to another Discord account
        if await db.is_email_already_verified(email):
            embed = discord.Embed(
                title="⚠️ Email Already Linked",
                description=config.ALREADY_VERIFIED,
                color=config.WARNING_COLOR
            )
            await db.log_verification_action(email, user.id, "VERIFY_REQUEST", "FAILED", "Email already linked")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Generate and send OTP
        otp = self.generate_otp()
        student_name = student.get("name", "Student")
        
        # Store OTP in database
        await db.store_otp(email, otp, user.id)
        
        # Send OTP email
        email_sent = await self.send_otp_email(email, otp, student_name)
        
        if email_sent:
            self.set_cooldown(user.id)
            embed = discord.Embed(
                title="📧 OTP Sent!",
                description=f"A verification code has been sent to:\n**{email}**\n\nPlease check your inbox (and spam folder).",
                color=config.EMBED_COLOR
            )
            embed.add_field(
                name="Next Step",
                value="Use `/otp code:XXXXXX` to complete verification.",
                inline=False
            )
            embed.add_field(
                name="⏰ Expires In",
                value="5 minutes",
                inline=True
            )
            embed.set_footer(text="Code not received? Wait 60 seconds and try again.")
            
            await db.log_verification_action(email, user.id, "OTP_SENT", "SUCCESS")
        else:
            embed = discord.Embed(
                title="❌ Error Sending Email",
                description="We couldn't send the verification email. Please try again later or contact support.",
                color=config.ERROR_COLOR
            )
            await db.log_verification_action(email, user.id, "OTP_SENT", "FAILED", "Email send failed")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="otp", description="Enter your OTP code to complete verification")
    @app_commands.describe(code="The 6-digit code sent to your email")
    async def otp(self, interaction: discord.Interaction, code: str):
        """
        Verify the OTP code and assign roles
        Uses new 4-column CSV format: Name, Email, Course (category), Batch (batch role)
        """
        await interaction.response.defer(ephemeral=True)
        
        user = interaction.user
        code = code.strip()
        
        logger.info(f"OTP verification attempt: {user.name} ({user.id})")
        
        # Verify OTP
        result = await db.verify_otp(user.id, code)
        
        if not result["valid"]:
            embed = discord.Embed(
                title="❌ Verification Failed",
                description=result["error"],
                color=config.ERROR_COLOR
            )
            await db.log_verification_action(result.get("email"), user.id, "OTP_VERIFY", "FAILED", result["error"])
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        email = result["email"]
        
        # OTP is valid - verify the student in database
        verified = await db.verify_student(email, user.id)
        
        if not verified:
            embed = discord.Embed(
                title="❌ Verification Error",
                description="An error occurred during verification. Please contact support.",
                color=config.ERROR_COLOR
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # ============================================
        # GET UNIVERSITY, COURSE & BATCH FROM DATABASE (New 5-column CSV format)
        # ============================================
        university, course, batch = await db.get_student_university_course_batch(email)
        
        roles_to_add = []
        role_assignment_errors = []
        
        # Add VERIFIED role (general access)
        if config.VERIFIED_ROLE_ID:
            verified_role = interaction.guild.get_role(config.VERIFIED_ROLE_ID)
            if verified_role:
                roles_to_add.append(verified_role)
            else:
                logger.warning(f"VERIFIED_ROLE_ID {config.VERIFIED_ROLE_ID} not found in guild. Check config.py")
                role_assignment_errors.append("Verified role not found")
        
        # ============================================
        # AUTO-CREATE UNIVERSITY/COURSE & BATCH RESOURCES
        # ============================================
        category = None
        
        if course:
            logger.info(f"Processing student: University='{university}', Course='{course}', Batch='{batch}'")
            
            # Step 1: Ensure Course resources exist (Category + shared channels) - now with university prefix
            course_role, category = await self.ensure_course_resources(interaction.guild, university, course)
            
            if course_role:
                roles_to_add.append(course_role)
                logger.info(f"Adding course role: {course_role.name}")
            else:
                role_assignment_errors.append(f"Could not create/find course role for '{university}-{course}' if university else '{course}'")
            
            # Step 2: Ensure Batch resources exist (Batch role + private channel) - now with university prefix
            if batch:
                batch_role = await self.ensure_batch_resources(
                    interaction.guild,
                    university,
                    course,
                    batch,
                    category
                )
                
                if batch_role:
                    roles_to_add.append(batch_role)
                    logger.info(f"Adding batch role: {batch_role.name}")
                else:
                    role_assignment_errors.append(f"Could not create/find batch role for '{university}-{batch}' if university else '{batch}'")
        else:
            logger.warning(f"No course found in database for email: {email}")
        
        # Assign roles to user
        assigned_roles = []
        try:
            if roles_to_add:
                await user.add_roles(*roles_to_add, reason=f"Email verified: {email}")
                assigned_roles = [r.name for r in roles_to_add]
                logger.info(f"Successfully assigned roles to {user.name} ({user.id}): {assigned_roles}")
            else:
                logger.warning(f"No roles to assign for {user.name} ({user.id}). Check role configuration.")
        except discord.Forbidden:
            logger.error(f"PERMISSION ERROR: Bot lacks permission to assign roles to {user.name}. "
                         f"Ensure bot role is ABOVE the roles it needs to assign in Server Settings → Roles.")
            role_assignment_errors.append("Bot lacks permission (check role hierarchy)")
        except discord.HTTPException as e:
            logger.error(f"Discord API error while assigning roles to {user.name}: {e}")
            role_assignment_errors.append(f"Discord API error: {e.status}")
        except Exception as e:
            logger.error(f"Unexpected error assigning roles to {user.name}: {type(e).__name__}: {e}")
            role_assignment_errors.append("Unexpected error")
        
        # Success message
        embed = discord.Embed(
            title="✅ Verification Successful!",
            description=config.VERIFICATION_SUCCESS.format(username=user.display_name),
            color=config.SUCCESS_COLOR
        )
        embed.add_field(name="Email", value=email, inline=True)
        if university:
            embed.add_field(name="University", value=university, inline=True)
        embed.add_field(name="Course", value=course or "N/A", inline=True)
        if batch:
            embed.add_field(name="Batch", value=batch, inline=True)
        
        # Show assigned roles
        if assigned_roles:
            embed.add_field(name="Roles Assigned", value=", ".join(assigned_roles), inline=False)
        
        # Warn user if there were any role assignment issues
        if role_assignment_errors:
            embed.add_field(
                name="⚠️ Notice", 
                value="Some roles couldn't be assigned. Contact an admin if you can't access your course channels.",
                inline=False
            )
            logger.warning(f"Role assignment issues for {user.name}: {role_assignment_errors}")
        
        embed.set_thumbnail(url=user.avatar.url if user.avatar else None)
        
        await db.log_verification_action(
            email, user.id, "VERIFICATION_COMPLETE", "SUCCESS", 
            f"University: {university}, Course: {course}, Batch: {batch}, Roles: {assigned_roles}, Errors: {role_assignment_errors or 'None'}"
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        # Log to admin channel
        log_channel = interaction.guild.get_channel(config.LOG_CHANNEL_ID)
        if log_channel:
            log_embed = discord.Embed(
                title="🎓 New Student Verified",
                color=config.SUCCESS_COLOR,
                timestamp=datetime.utcnow()
            )
            log_embed.add_field(name="User", value=f"{user.mention} ({user.name})", inline=True)
            log_embed.add_field(name="Email", value=email, inline=True)
            if university:
                log_embed.add_field(name="University", value=university, inline=True)
            log_embed.add_field(name="Course", value=course or "N/A", inline=True)
            if batch:
                log_embed.add_field(name="Batch", value=batch, inline=True)
            log_embed.set_footer(text=f"User ID: {user.id}")
            
            try:
                await log_channel.send(embed=log_embed)
            except Exception as e:
                logger.error(f"Failed to send log message: {e}")
    
    @app_commands.command(name="reverify", description="Request a new verification code")
    async def reverify(self, interaction: discord.Interaction):
        """Allow users to request re-verification if they have a pending OTP"""
        await interaction.response.defer(ephemeral=True)
        
        user = interaction.user
        
        # Check if user has a pending OTP
        pending = await db.get_pending_otp(user.id)
        
        if not pending:
            embed = discord.Embed(
                title="ℹ️ No Pending Verification",
                description="You don't have a pending verification.\nUse `/verify email:your@email.com` to start.",
                color=config.EMBED_COLOR
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Check cooldown
        on_cooldown, remaining = self.is_on_cooldown(user.id)
        if on_cooldown:
            embed = discord.Embed(
                title="⏳ Please Wait",
                description=f"You can request another OTP in **{remaining}** seconds.",
                color=config.WARNING_COLOR
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        email = pending["email"]
        student = await db.get_student_by_email(email)
        
        # Generate and send new OTP
        otp = self.generate_otp()
        await db.store_otp(email, otp, user.id)
        
        email_sent = await self.send_otp_email(email, otp, student.get("name", "Student") if student else "Student")
        
        if email_sent:
            self.set_cooldown(user.id)
            embed = discord.Embed(
                title="📧 New OTP Sent!",
                description=f"A new verification code has been sent to:\n**{email}**",
                color=config.EMBED_COLOR
            )
            embed.add_field(name="Next Step", value="Use `/otp code:XXXXXX` to complete verification.", inline=False)
        else:
            embed = discord.Embed(
                title="❌ Error",
                description="Failed to send new OTP. Please try again later.",
                color=config.ERROR_COLOR
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    """Setup function to add the cog to the bot"""
    await bot.add_cog(Verification(bot))
