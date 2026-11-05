"""Survey-specific preparation with an explicit provider boundary; no scheduling.

Ingestion in this increment always supplies SimulatedSurveySender. The Resend
adapter reuses the existing transport and is tested through a mocked transport.
No CLI/HTTP switch enables it, and it refuses persisted simulated invitations.
"""
from html import escape


def prepare_invitation(*, name: str, community_name: str, survey_url: str, unsubscribe_url: str,
                       questionnaire: dict | None = None) -> dict:
    if questionnaire and questionnaire['event_type'] != 'maintenance_completed':
        # Reuse the approved questionnaire title rather than inventing invitation copy.
        title = questionnaire['title']
        subject = f'{community_name}: {title}'
        text = (f'Hello {name},\n\n{title}\n{survey_url}\n\n'
                f'Stop survey invitations: {unsubscribe_url}')
        html = (f'<p>Hello {escape(name)},</p><p>{escape(title)}</p>'
                f'<p><a href="{escape(survey_url, quote=True)}">Open your survey</a></p>'
                f'<p><a href="{escape(unsubscribe_url, quote=True)}">Stop survey invitations</a></p>')
        return {'subject': subject, 'html': html, 'text': text}
    subject = f'{community_name}: tell us about your maintenance experience'
    text = (f'Hello {name},\n\nPlease tell us about your maintenance experience at {community_name}.\n'
            f'{survey_url}\n\nStop survey invitations: {unsubscribe_url}')
    html = (f'<p>Hello {escape(name)},</p><p>Please tell us about your maintenance experience at '
            f'{escape(community_name)}.</p><p><a href="{escape(survey_url, quote=True)}">Open your survey</a></p>'
            f'<p><a href="{escape(unsubscribe_url, quote=True)}">Stop survey invitations</a></p>')
    return {'subject': subject, 'html': html, 'text': text}


class SimulatedSurveySender:
    def send(self, invitation) -> str:
        if not invitation.is_simulated:
            raise ValueError('The simulated sender only accepts simulated invitations')
        return 'simulated'


class ResendSurveySender:
    def send(self, invitation, *, allow_live: bool = False) -> str:
        if not allow_live or invitation.is_simulated:
            raise ValueError('Live survey delivery is disabled for this increment')
        from src.services import email_service
        accepted = email_service._send_email(
            to=invitation.recipient, subject=invitation.subject,
            html=invitation.html, text=invitation.text)
        return 'provider_accepted' if accepted else 'provider_failed'
