"""
Centralized email service with retry logic and error handling.
Supports both development (console) and production (SES) backends.
"""
import logging
import time
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, send_mail
from django.template.loader import render_to_string

from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class EmailService:
    """
    Centralized email service with exponential backoff retry logic.
    Handles SES quota limits and transient failures gracefully.
    """

    MAX_RETRIES = 3
    INITIAL_BACKOFF = 1  # seconds

    @classmethod
    def send_email(
        cls,
        subject: str,
        message: str,
        recipient_list: List[str],
        html_message: Optional[str] = None,
        from_email: Optional[str] = None,
        fail_silently: bool = False,
        retry: bool = True,
    ) -> bool:
        """
        Send email with retry logic and error handling.

        Args:
            subject: Email subject line
            message: Plain text message
            recipient_list: List of recipient email addresses
            html_message: Optional HTML version of message
            from_email: Sender email (uses DEFAULT_FROM_EMAIL if None)
            fail_silently: If False, raises exception on failure
            retry: Enable exponential backoff retry logic

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        if not recipient_list:
            logger.warning("Email not sent: recipient_list is empty")
            return False

        from_email = from_email or settings.DEFAULT_FROM_EMAIL

        for attempt in range(cls.MAX_RETRIES if retry else 1):
            try:
                if html_message:
                    email = EmailMultiAlternatives(
                        subject=subject,
                        body=message,
                        from_email=from_email,
                        to=recipient_list,
                    )
                    email.attach_alternative(html_message, "text/html")
                    email.send(fail_silently=False)
                else:
                    send_mail(
                        subject=subject,
                        message=message,
                        from_email=from_email,
                        recipient_list=recipient_list,
                        fail_silently=False,
                    )

                logger.info(f"Email sent successfully: '{subject}' to {recipient_list}")
                return True

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")

                # Handle SES-specific errors
                if error_code == "Throttling":
                    if attempt < cls.MAX_RETRIES - 1:
                        backoff = cls.INITIAL_BACKOFF * (2**attempt)
                        logger.warning(
                            f"SES throttling detected. "
                            f"Retrying in {backoff}s (attempt {attempt + 1})"
                        )
                        time.sleep(backoff)
                        continue
                    else:
                        logger.error(
                            f"Email failed after {cls.MAX_RETRIES} retries "
                            f"due to throttling"
                        )

                elif error_code == "MessageRejected":
                    logger.error(f"SES rejected email: {str(e)}")

                elif error_code == "MailFromDomainNotVerified":
                    logger.error(
                        "SES sender email not verified. "
                        "Verify sender in AWS SES console."
                    )

                else:
                    logger.error(f"SES ClientError: {error_code} - {str(e)}")

                if not fail_silently:
                    raise
                return False

            except Exception as e:
                logger.error(f"Failed to send email: {str(e)}")

                if attempt < cls.MAX_RETRIES - 1 and retry:
                    backoff = cls.INITIAL_BACKOFF * (2**attempt)
                    logger.info(f"Retrying in {backoff}s (attempt {attempt + 1})")
                    time.sleep(backoff)
                    continue

                if not fail_silently:
                    raise
                return False

        return False

    @classmethod
    def send_welcome_email(cls, user, verification_url: Optional[str] = None) -> bool:
        """Send welcome email to newly registered user."""
        subject = f"Welcome to FICCT-SCRUM, {user.first_name}!"

        message = f"""
Hi {user.first_name},

Welcome to FICCT-SCRUM! Your account has been successfully created.

Email: {user.email}
Username: {user.username}

Get started by creating your first organization and inviting team members.

Best regards,
The FICCT-SCRUM Team
"""

        html_message = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <h2 style="color: #4A90E2;">Welcome to FICCT-SCRUM!</h2>
    <p>Hi <strong>{user.first_name}</strong>,</p>
    <p>Your account has been successfully created.</p>
    <ul>
        <li><strong>Email:</strong> {user.email}</li>
        <li><strong>Username:</strong> {user.username}</li>
    </ul>
    <p>Get started by creating your first organization and inviting team members.</p>
    <p style="margin-top: 30px;">Best regards,<br>The FICCT-SCRUM Team</p>
</body>
</html>
"""

        return cls.send_email(
            subject=subject,
            message=message,
            recipient_list=[user.email],
            html_message=html_message,
        )

    @classmethod
    def send_password_reset_email(
        cls, user, reset_token: str, frontend_url: Optional[str] = None
    ) -> bool:
        """Send password reset email with token link."""
        frontend_url = frontend_url or getattr(
            settings, "FRONTEND_URL", "http://localhost:4200"
        )
        reset_url = f"{frontend_url}/reset-password/{reset_token}"

        subject = "Password Reset Request - FICCT-SCRUM"

        message = f"""
Hi {user.first_name},

You requested to reset your password for your FICCT-SCRUM account.

Click the link below to reset your password:
{reset_url}

This link will expire in 1 hour.

If you didn't request this, please ignore this email.

Best regards,
The FICCT-SCRUM Team
"""

        html_message = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <h2 style="color: #4A90E2;">Password Reset Request</h2>
    <p>Hi <strong>{user.first_name}</strong>,</p>
    <p>You requested to reset your password for your FICCT-SCRUM account.</p>
    <p>
        <a href="{reset_url}" 
           style="background-color: #4A90E2; color: white; padding: 12px 24px; 
                  text-decoration: none; border-radius: 4px; display: inline-block;">
            Reset Password
        </a>
    </p>
    <p style="color: #666; font-size: 14px;">This link will expire in 1 hour.</p>
    <p style="color: #666; font-size: 14px;">
        If you didn't request this, please ignore this email.
    </p>
    <p style="margin-top: 30px;">Best regards,<br>The FICCT-SCRUM Team</p>
</body>
</html>
"""

        return cls.send_email(
            subject=subject,
            message=message,
            recipient_list=[user.email],
            html_message=html_message,
        )

    @classmethod
    def send_organization_invitation_email(
        cls,
        invitation,
        invited_by_name: str,
        organization_name: str,
        frontend_url: Optional[str] = None,
    ) -> bool:
        """Send organization invitation email for new users."""
        frontend_url = frontend_url or getattr(
            settings, "FRONTEND_URL", "http://localhost:4200"
        )
        invite_url = f"{frontend_url}/accept-invitation?token={invitation.token}"

        subject = f"Te han invitado a {organization_name} en FICCT-SCRUM"

        message = f"""
Hola,

{invited_by_name} te ha invitado a unirte a la organización 
"{organization_name}" en FICCT-SCRUM como {invitation.get_role_display()}.

Para aceptar esta invitación, haz click en el siguiente enlace:

{invite_url}

Si no tienes cuenta en FICCT-SCRUM, el enlace te guiará 
para crear una usando este email: {invitation.email}

Esta invitación expira el {invitation.expires_at.strftime('%d de %B de %Y')}.

---
Equipo FICCT-SCRUM
https://scrum.ficct.com
"""

        html_message = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto;">
    <div style="background-color: #4A90E2; padding: 20px; text-align: center;">
        <h1 style="color: white; margin: 0;">FICCT-SCRUM</h1>
    </div>
    <div style="padding: 30px; background-color: #f9f9f9;">
        <h2 style="color: #4A90E2;">¡Te han invitado!</h2>
        <p><strong>{invited_by_name}</strong> te ha invitado a unirte a la organización 
           <strong>{organization_name}</strong> en FICCT-SCRUM.</p>
        <p><strong>Rol:</strong> {invitation.get_role_display()}</p>
        {f'<p style="color: #666;"><strong>Mensaje:</strong> {invitation.message}</p>' if invitation.message else ''}
        <p style="text-align: center; margin: 30px 0;">
            <a href="{invite_url}" 
               style="background-color: #4A90E2; color: white; padding: 14px 28px; 
                      text-decoration: none; border-radius: 6px; display: inline-block; font-weight: bold;">
                Aceptar Invitación
            </a>
        </p>
        <p style="color: #666; font-size: 13px; border-left: 3px solid #4A90E2; padding-left: 15px;">
            <strong>Nota:</strong> Si no tienes cuenta en FICCT-SCRUM, el enlace te guiará para crear una 
            usando el email: <strong>{invitation.email}</strong>
        </p>
        <p style="color: #999; font-size: 12px; text-align: center; margin-top: 30px;">
            Esta invitación expira el {invitation.expires_at.strftime('%d de %B de %Y')}
        </p>
    </div>
    <div style="background-color: #333; color: white; padding: 15px; text-align: center; font-size: 12px;">
        <p style="margin: 0;">Equipo FICCT-SCRUM | scrum.ficct.com</p>
    </div>
</body>
</html>
"""

        return cls.send_email(
            subject=subject,
            message=message,
            recipient_list=[invitation.email],
            html_message=html_message,
        )

    @classmethod
    def send_organization_member_added_email(
        cls,
        user,
        organization,
        role: str,
        invited_by_name: str,
        frontend_url: Optional[str] = None,
    ) -> bool:
        """Send email to existing user when added directly to organization."""
        frontend_url = frontend_url or getattr(
            settings, "FRONTEND_URL", "http://localhost:4200"
        )
        dashboard_url = f"{frontend_url}/organizations/{organization.id}/dashboard"

        # Get role display name
        role_display = dict(
            [
                ("owner", "Owner"),
                ("admin", "Administrador"),
                ("manager", "Manager"),
                ("member", "Miembro"),
                ("guest", "Invitado"),
            ]
        ).get(role, role)

        subject = f"Te agregaron a {organization.name} en FICCT-SCRUM"

        message = f"""
Hola {user.first_name},

{invited_by_name} te ha agregado a la organización "{organization.name}" 
en FICCT-SCRUM como {role_display}.

Ahora puedes:
- Ver y participar en workspaces de la organización
- Colaborar en proyectos del equipo
- Gestionar issues y sprints

Comienza aquí: {dashboard_url}

---
Equipo FICCT-SCRUM
https://scrum.ficct.com
"""

        html_message = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto;">
    <div style="background-color: #4A90E2; padding: 20px; text-align: center;">
        <h1 style="color: white; margin: 0;">FICCT-SCRUM</h1>
    </div>
    <div style="padding: 30px; background-color: #f9f9f9;">
        <h2 style="color: #4A90E2;">¡Te agregaron a una organización!</h2>
        <p>Hola <strong>{user.first_name}</strong>,</p>
        <p><strong>{invited_by_name}</strong> te ha agregado a la organización 
           <strong>{organization.name}</strong> como <strong>{role_display}</strong>.</p>
        
        <div style="background-color: white; padding: 20px; border-radius: 6px; margin: 20px 0;">
            <h3 style="color: #333; margin-top: 0;">Ahora puedes:</h3>
            <ul style="color: #666;">
                <li>Ver y participar en workspaces de la organización</li>
                <li>Colaborar en proyectos del equipo</li>
                <li>Gestionar issues y sprints</li>
            </ul>
        </div>

        <p style="text-align: center; margin: 30px 0;">
            <a href="{dashboard_url}" 
               style="background-color: #4A90E2; color: white; padding: 14px 28px; 
                      text-decoration: none; border-radius: 6px; display: inline-block; font-weight: bold;">
                Ir al Dashboard
            </a>
        </p>
    </div>
    <div style="background-color: #333; color: white; padding: 15px; text-align: center; font-size: 12px;">
        <p style="margin: 0;">Equipo FICCT-SCRUM | scrum.ficct.com</p>
    </div>
</body>
</html>
"""

        return cls.send_email(
            subject=subject,
            message=message,
            recipient_list=[user.email],
            html_message=html_message,
        )

    @classmethod
    def send_organization_welcome_email(
        cls, user, organization, role: str, frontend_url: Optional[str] = None
    ) -> bool:
        """Send welcome email after user accepts invitation."""
        frontend_url = frontend_url or getattr(
            settings, "FRONTEND_URL", "http://localhost:4200"
        )
        dashboard_url = f"{frontend_url}/organizations/{organization.id}/dashboard"

        # Get role display name
        role_display = dict(
            [
                ("owner", "Owner"),
                ("admin", "Administrador"),
                ("manager", "Manager"),
                ("member", "Miembro"),
                ("guest", "Invitado"),
            ]
        ).get(role, role)

        subject = f"Bienvenido a {organization.name}"

        message = f"""
¡Hola {user.first_name}!

Te has unido exitosamente a "{organization.name}" como {role_display}.

Ahora puedes:
- Ver y participar en workspaces de la organización
- Colaborar en proyectos del equipo
- Gestionar issues y sprints

Comienza aquí: {dashboard_url}

---
Equipo FICCT-SCRUM
https://scrum.ficct.com
"""

        html_message = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto;">
    <div style="background-color: #4A90E2; padding: 20px; text-align: center;">
        <h1 style="color: white; margin: 0;">FICCT-SCRUM</h1>
    </div>
    <div style="padding: 30px; background-color: #f9f9f9;">
        <h2 style="color: #4A90E2;">¡Bienvenido a {organization.name}!</h2>
        <p>¡Hola <strong>{user.first_name}</strong>!</p>
        <p>Te has unido exitosamente a <strong>{organization.name}</strong> como <strong>{role_display}</strong>.</p>
        
        <div style="background-color: white; padding: 20px; border-radius: 6px; margin: 20px 0;">
            <h3 style="color: #333; margin-top: 0;">Ahora puedes:</h3>
            <ul style="color: #666;">
                <li>Ver y participar en workspaces de la organización</li>
                <li>Colaborar en proyectos del equipo</li>
                <li>Gestionar issues y sprints</li>
            </ul>
        </div>

        <p style="text-align: center; margin: 30px 0;">
            <a href="{dashboard_url}" 
               style="background-color: #4A90E2; color: white; padding: 14px 28px; 
                      text-decoration: none; border-radius: 6px; display: inline-block; font-weight: bold;">
                Comenzar Ahora
            </a>
        </p>
    </div>
    <div style="background-color: #333; color: white; padding: 15px; text-align: center; font-size: 12px;">
        <p style="margin: 0;">Equipo FICCT-SCRUM | scrum.ficct.com</p>
    </div>
</body>
</html>
"""

        return cls.send_email(
            subject=subject,
            message=message,
            recipient_list=[user.email],
            html_message=html_message,
        )

    @classmethod
    def get_ses_statistics(cls) -> Dict[str, Any]:
        """Get SES sending statistics (quota, sent count, etc.)."""
        try:
            import boto3
            from botocore.exceptions import ClientError

            ses_client = boto3.client(
                "ses",
                region_name=settings.AWS_SES_REGION_NAME,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            )

            quota = ses_client.get_send_quota()
            statistics = ses_client.get_send_statistics()

            return {
                "max_24_hour_send": quota.get("Max24HourSend", 0),
                "sent_last_24_hours": quota.get("SentLast24Hours", 0),
                "max_send_rate": quota.get("MaxSendRate", 0),
                "data_points": statistics.get("SendDataPoints", []),
            }

        except Exception as e:
            logger.error(f"Failed to get SES statistics: {str(e)}")
            return {}
