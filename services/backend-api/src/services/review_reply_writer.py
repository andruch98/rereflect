"""Generate a single public reply from one review and one community's settings."""
import json
import os
import re
from pathlib import Path

import openai

from src.services.agent_settings import ReviewSettings
from src.services.ask_genius import configured_llm
from src.services.copilot.llm_resolver import resolve_generation_llm

INSTRUCTIONS = Path(__file__).with_name('review_reply_instructions.txt').read_text(encoding='utf-8')

# These conservative holds only route replies to a human. They never label
# the reviewer or adjudicate whether their concern is true.
HOLD_PATTERNS = {
    'safety': r'\b(safe(?:ty)?|unsafe|hazard\w*|slipp?ed|injur\w*|threat\w*|fire|gas leak|mold|break[- ]?in|broken lock|unlocked|security|assault\w*|attack\w*|smoke alarm|emergency exit|(?:door|gate).{0,35}(?:won.t|doesn.t|does not|fails? to) (?:lock|latch)|(?:lock|latch).{0,20}(?:broken|stuck|doesn.t work))\b',
    'billing': r'\b(bill\w*|fees?|charges?|charged|deposit|refund\w*|overcharg\w*|rent|payments?)\b',
    'legal': r'\b(legal|attorney|lawyer|lawsuit|suing|sue|court|illegal|discriminat\w*|evict\w*|fair housing)\b',
    'staff_allegations': r'\b(harass\w*|threat\w*|racis\w*|discriminat\w*|retaliat\w*|assault\w*|stole|rude|abus\w*|misconduct|intimidat\w*)\b',
}
TOPIC_LABELS = {'staff_allegations': 'staff allegations', 'legal': 'legal concerns',
                'safety': 'safety', 'billing': 'billing'}


class ReviewWriterError(Exception):
    """A safe, manager-facing drafting error."""


def approval_policy(settings, text, stars):
    holds = [TOPIC_LABELS[topic] for topic in settings.hold_topics
             if re.search(HOLD_PATTERNS[topic], text or '', re.IGNORECASE)]
    if stars is not None and stars <= settings.hold_at_or_below:
        holds.insert(0, f'{stars}-star rating')
    if holds:
        return 'pending_approval', 'Requires manager approval for ' + ', '.join(holds) + '.'
    if settings.mode == 'approval':
        return 'pending_approval', 'Your community requires manager approval for every reply.'
    return 'approved', 'Approved automatically under your community settings.'


def example_body(settings, review, stars):
    """Offline preview text, clearly labeled in the UI rather than attributed to AI."""
    if re.search(r'\bbroken lock\b', review, re.IGNORECASE):
        return ('Thank you for bringing this concern to our attention. '
                'Please visit our office or call so we can arrange a maintenance '
                'to come and fix the broken lock asap.')
    concern = any(re.search(pattern, review, re.I) for pattern in HOLD_PATTERNS.values())
    if stars and stars <= 3:
        concern = True
    if concern:
        opening = {'concise': 'Thank you for raising this.', 'warm': 'We appreciate you letting us know.',
                   'professional': 'Thank you for bringing this concern to our attention.'}[settings.tone]
        contact = ' or '.join(filter(None, [settings.public_email, settings.public_phone]))
        return opening + (' Please contact our team at ' + contact + ' to discuss it privately.' if contact
                          else ' Our team welcomes the opportunity to discuss this privately.')
    return {
        'concise': 'Thank you for sharing your feedback.',
        'warm': f'We appreciate you taking the time to share your experience at {settings.community_name}. Thank you!',
        'professional': f'Thank you for sharing your feedback about {settings.community_name}.',
    }[settings.tone]


def confirmed_contacts(body, settings):
    emails = re.findall(r"[\w.+%-]+@[\w.-]+\.[A-Za-z]{2,}", body)
    for address in emails:
        if address.casefold() != settings.public_email.casefold():
            raise ReviewWriterError('The draft contains an unconfirmed public email.')
    # Validate the number and any extension separately. An optional US country
    # prefix or punctuation cannot change a manager's verified office number.
    phone_pattern = r"(?<!\w)\+?\(?\d(?:[ ().-]{0,3}\d){6,14}(?:\s*(?:ext(?:ension)?\.?|x)\s*\d+)?(?!\w)"
    def phone_parts(number):
        main, *extension = re.split(r"\s*(?:ext(?:ension)?\.?|x)\s*", number, flags=re.IGNORECASE)
        digits = re.sub(r"\D", "", main)
        if len(digits) == 11 and digits.startswith('1'):
            digits = digits[1:]
        return digits, extension[0] if extension else ''
    verified, verified_extension = phone_parts(settings.public_phone)
    for match in re.finditer(phone_pattern, body, re.IGNORECASE):
        digits, extension = phone_parts(match.group())
        if digits != verified or (extension and extension != verified_extension):
            raise ReviewWriterError('The draft contains an unconfirmed public phone number.')


async def write_reply(db, org_id, settings: ReviewSettings, review, stars, author=None):
    preview = os.getenv('BOOMSAY_REVIEW_PREVIEW', '').lower() == 'true'
    if preview:
        config, _ = configured_llm(org_id, db)
    else:
        config = resolve_generation_llm(org_id, db)

    if config and config.is_configured:
        if config.provider not in {'openai', 'openai_compatible', 'ollama'}:
            raise ReviewWriterError('The review writer does not support this provider yet.')
        community = settings.model_dump(include={'community_name', 'public_email', 'public_phone', 'facts',
                                                 'tone', 'praise_guidance', 'complaint_guidance'})
        messages = [{'role': 'system', 'content': INSTRUCTIONS},
                    {'role': 'user', 'content': json.dumps({'community': community,
                        'review': {'text': review, 'stars': stars}}, ensure_ascii=False)}]
        async with openai.AsyncOpenAI(base_url=config.base_url, api_key=config.api_key or 'local-keyless',
                                      timeout=30.0, max_retries=0) as client:
            result = await client.chat.completions.create(model=config.model, messages=messages, max_completion_tokens=350)
        choice = result.choices[0] if result.choices else None
        if not choice or choice.finish_reason != 'stop' or getattr(choice.message, 'refusal', None):
            raise ReviewWriterError('The response writer could not complete a draft.')
        body = (choice.message.content or '').strip()
        if not body or len(body) > 4000:
            raise ReviewWriterError('The response writer returned an incomplete draft.')
        confirmed_contacts(body, settings)
        usage = {'provider': config.provider, 'model': config.model,
                 'input_tokens': result.usage.prompt_tokens if result.usage else None,
                 'output_tokens': result.usage.completion_tokens if result.usage else None}
        method = 'ai'
    elif preview and os.getenv('ASK_GENIUS_ENABLED', '').lower() != 'true':
        body, method, usage = example_body(settings, review, stars), 'example', None
    else:
        raise ReviewWriterError('The community’s response writer needs a configured AI connection.')

    # Add names locally, using only this review's public display name.
    if isinstance(author, str) and 0 < len(author) <= 80 and all(c.isalpha() or c in " -'’." for c in author):
        body = f'{author.strip()},\n\n{body}' if author.strip() else body
    if settings.signature:
        body += '\n\n' + settings.signature
    return body, method, usage
