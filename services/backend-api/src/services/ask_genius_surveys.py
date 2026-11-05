"""Read finalized survey originals for Ask Genius; never analyze or mutate them."""
from __future__ import annotations

import re
from collections import Counter
from copy import deepcopy
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from src.services.ask_genius_periods import TIMEZONE, resolve_period
from src.services.survey_catalog import EVENT_LABELS, event_type_for

MAX_SURVEYS = 100
TYPE_PATTERNS = {
    'move_in_completed': r'move[ -]?in(?: completed)?',
    'maintenance_completed': r'(?:maintenance|work[ -]?order)(?: completed)?',
    'lease_month_3': r'(?:3|three)[ -]?month',
    'lease_month_6': r'(?:6|six)[ -]?month',
    'lease_month_9': r'(?:9|nine)[ -]?month(?: renewal (?:planning|intent))?|pre[ -]?renewal|renewal intent',
    'lease_renewed': r'(?:lease |completed |signed )?renewal|renewed lease',
    'move_out_completed': r'move[ -]?out(?: completed)?',
}


def _type_selections(text):
    """Recognize named questionnaire types, including shared-noun lists."""
    pattern = '(?:' + '|'.join('(?:' + item + ')' for item in TYPE_PATTERNS.values()) + ')'
    group = pattern + r'(?:(?:\s*,\s*(?:and\s+)?|\s+(?:and|or)\s+)' + pattern + ')*'
    for match in re.finditer(r'\b' + group + r'\b', text):
        before, after = text[:match.start()], text[match.end():]
        exclusion = re.search(r'\b(?:not|exclude|excluding|without|except)\s*$', before)
        direct = re.match(r'\s+(?:survey|questionnaire|submission|response)s?\b', after)
        after_type = re.search(r'(?:surveys?|questionnaires?|submissions?|responses?) (?:for|from|after)\s*$', before)
        short = re.fullmatch(r'(?:what about (?:the )?|(?:use|show|only) (?:the )?)?' + group + r'[?.! ]*', text)
        description = (re.fullmatch(r'(?:please )?what (?:does|do|did) (?:the )?', before)
                       and re.match(r'\s+(?:say|report|show)\b', after))
        # "surveys excluding maintenance" has no repeated noun after the type.
        excluded_tail = exclusion and re.search(r'\b(?:surveys?|submissions?|questionnaires?)\b', before)
        if not (direct or after_type or short or description or excluded_tail):
            continue
        kinds, occupied = set(), []
        for kind, item in TYPE_PATTERNS.items():
            for found in re.finditer(r'\b(?:' + item + r')\b', match.group()):
                if not any(start <= found.start() < end for start, end in occupied):
                    kinds.add(kind)
                    occupied.append(found.span())
        yield match, kinds, exclusion, direct, after_type


def survey_types(question: str, previous=None):
    """A survey topic is not a questionnaire type; ordinary follow-ups keep scope."""
    text = question.casefold()
    included, excluded = set(), set()
    for match, kinds, exclusion, _, _ in _type_selections(text):
        if re.search(r'\bor\b', match.group()):
            raise ValueError('Choose one survey type, or use “and” to include both survey types.')
        (excluded if exclusion else included).update(kinds)
    all_types = re.search(r'\b(?:all|every) (?:survey types?|types? of surveys?|surveys?)\b', text)
    # An unqualified evaluation of plural surveys starts a broad comparison;
    # "what does the bad say?" remains a follow-up to the selected type.
    evaluation = r'(?:bad|good|negative|positive|(?:low|poorly|high)[ -]rated)'
    units = r'(?:surveys|submissions|responses|questionnaires)'
    broad_evaluation = re.search(
        r'\b(?:(?:which (?:are|were)|show(?: me)?|list|summarize|display) (?:the )?'
        + evaluation + ' ' + units + '|' + 'which (?:of (?:the )?)?' + units
        + r' (?:are|were) ' + evaluation + r')\b', text)
    if excluded:
        selected = (set(EVENT_LABELS) if all_types or not included else included) - excluded
        if not selected:
            raise ValueError('No survey types remain after those exclusions. Choose at least one survey type.')
        return sorted(selected)
    return sorted(included) if included else ([] if all_types or broad_evaluation else list(previous or []))


def _context(record):
    return record.get('context', record.get('maintenance_context', {}))


def calculated(records):
    rating_counts = {}
    for record in records:
        for question in record['questions']:
            if question.get('type') != 'rating' or question.get('answer') is None:
                continue
            counts = rating_counts.setdefault(record.get('event_type', 'maintenance_completed'), {}).setdefault(question['id'], {})
            label = question['answer_label']
            counts[label] = counts.get(label, 0) + 1
    maintenance = [r for r in records if r.get('event_type', 'maintenance_completed') == 'maintenance_completed']
    resolutions = {r['survey_id']: next((q['answer'] for q in r['questions'] if q['id'] == 'issue_resolution'), None)
                   for r in maintenance}
    values = [value for value in resolutions.values() if value is not None]
    return {
        'submission_count': len(records),
        'distinct_resident_count': len({_context(r)['resident_id'] for r in records}),
        'survey_type_counts': dict(Counter(r.get('event_type', 'maintenance_completed') for r in records)),
        'rating_counts_by_type': rating_counts,
        'issue_resolution_counts': dict(Counter(values)),
        'issue_resolution_submission_ids': {value: [key for key, answer in resolutions.items() if answer == value]
                                           for value in dict.fromkeys(values)},
    }


def needs_findings(question: str, evidence: dict) -> bool:
    """Require a source-linked coverage pass for broad survey assessments only.

    This selects a response format, never records or sentiment. Existing scope
    resolution still determines the entire supplied cohort.
    """
    if evidence.get('source_scope') not in {'surveys', 'mixed'} or not evidence.get('surveys'):
        return False
    text = re.sub(r'\s+', ' ', question.casefold())
    patterns = (
        r'\b(?:bad|negative|poor|low[ -]rated|concerning) surveys?\b',
        r'\b(?:surveys?|submissions?|responses?)\b.{0,35}\b(?:bad|negative|need(?:s)? attention)\b',
        r'\b(?:improvements?|complaints?|concerns?|problems?)\b.{0,60}\b(?:all|every) surveys?\b',
        r'\b(?:all|every) surveys?\b.{0,60}\b(?:improvements?|complaints?|concerns?|problems?)\b',
        r'\b(?:main|biggest|top|key) (?:improvements?|complaints?|concerns?|problems?)\b',
        r'\b(?:are we|how are we) doing\b',
        r'\b(?:overall|general) (?:assessment|summary|performance|feedback)\b',
        r'\b(?:summarize|summary of|overview of|what do|what did|compare)\b.{0,50}\b(?:all|every) (?:surveys?|survey responses?|feedback)\b',
    )
    return any(re.search(pattern, text) for pattern in patterns)


def source_scope(question: str, previous: str | None = None) -> str | None:
    """Resolve named sources, never infer a source from the subject (e.g. maintenance).

    Exclusions take precedence over mentions. An ambiguous choice is clarified rather
    than silently reading a different source. Conversation scope is the fallback.
    """
    groups = {'reviews': r'reviews?', 'surveys': r'(?:surveys?|submissions?|questionnaires?)'}
    included, excluded = set(), set()
    for name, pattern in groups.items():
        for match in re.finditer(r'\b' + pattern + r'\b', question, re.I):
            before = question[:match.start()].lower()
            if re.search(r"(?:\bnot|\bexcluding|\bexclude|\bwithout|\bignore|\binstead of|\brather than|\bdon['’]t (?:use|include))\s+(?:the\s+)?$", before):
                excluded.add(name)
            else:
                included.add(name)
    included -= excluded
    if len(included) == 2 and re.search(r'\b(?:reviews?\s+or\s+(?:surveys?|submissions?)|(?:surveys?|submissions?)\s+or\s+reviews?)\b', question, re.I):
        return None
    if len(included) == 2:
        return 'mixed'
    if included:
        return included.pop()
    if excluded:
        return ({'reviews', 'surveys'} - excluded).pop() if len(excluded) == 1 else None
    if re.fullmatch(r'(?:use |include )?both(?: sources)?[.! ]*', question.strip(), re.I):
        return 'mixed'
    return previous if previous in {'reviews', 'surveys', 'mixed'} else None


def source_choice(question: str) -> bool:
    """A short clarification reply resumes the original question, not a new task."""
    return bool(re.fullmatch(r'(?:use |include |just |only )?(?:reviews?|surveys?|both)(?: only| sources)?(?:,? not (?:reviews?|surveys?))?(?:,? please)?[.! ]*', question.strip(), re.I))


def topic_lines(answer: str, references: list[dict], previous: dict | None = None) -> dict:
    """Retain concise finding text alongside its references through count follow-ups."""
    result = {}
    for topic in dict.fromkeys(item.get('topic') for item in references if item.get('topic')):
        line = next((line for line in answer.splitlines() if re.match(
            r'^\s*[-*+]\s+(?:\*\*)?' + re.escape(topic) + r'(?:\*\*)?:', line)), None)
        if line:
            result[topic] = line
        elif topic in (previous or {}):
            result[topic] = previous[topic]
    return result


def _iso(value):
    return value.replace(tzinfo=value.tzinfo or timezone.utc).isoformat() if value else None


def original_record(row) -> dict:
    snapshot = row.questionnaire_snapshot
    questions = []
    for question in snapshot['questions']:
        answer = row.answers.get(question['id'])
        labels = snapshot.get('rating_labels', {})
        choices = question.get('options', [])
        if isinstance(choices, dict):
            choices = [{'value': key, 'label': value} for key, value in choices.items()]
        choices = [*choices, *question.get('special_options', [])]
        label = next((choice['label'] for choice in choices if choice['value'] == answer), None)
        if type(answer) is int:
            label = f'{answer} — {labels.get(str(answer), labels.get(answer, ""))}'.rstrip(' —')
        if label is None:
            label = answer if isinstance(answer, str) else None
        questions.append({**question, 'original_text': question['text'], 'text': question.get('rendered_text', question['text']),
                          'rating_labels': labels if question.get('type') == 'rating' else None,
                          'answer': answer, 'answer_label': label})
    return {'survey_id': row.public_id, 'submitted_at': _iso(row.submitted_at),
            'template_id': snapshot['id'], 'template_version': snapshot['version'],
            'event_type': event_type_for(snapshot, row.context_snapshot),
            'survey_type_label': EVENT_LABELS.get(event_type_for(snapshot, row.context_snapshot), 'Survey'),
            'title': snapshot.get('title', 'Survey'), 'context': row.context_snapshot,
            'maintenance_context': row.context_snapshot, 'questions': questions,
            'saved_analysis': {'status': 'not_generated'}}


def model_record(record: dict) -> dict:
    """Present each bound question and context once, without changing originals.

    Source cards and validation retain the full record. Keep answer codes and
    display labels, all choices, and rating scales; never summarize resident text.
    """
    result = deepcopy(record)
    if result.get('maintenance_context') == result.get('context'):
        result.pop('maintenance_context', None)
    for question in result['questions']:
        # text already contains the exact bound wording shown to the resident.
        for key in ('rendered_text', 'original_text', 'required', 'max_length'):
            question.pop(key, None)
        if question.get('rating_labels') is None:
            question.pop('rating_labels', None)
        if question.get('type') == 'text' and question.get('answer_label') == question.get('answer'):
            question.pop('answer_label', None)
    scales = [q['rating_labels'] for q in result['questions'] if 'rating_labels' in q]
    if scales and all(scale == scales[0] for scale in scales):
        result['rating_labels'] = scales[0]
        for question in result['questions']:
            question.pop('rating_labels', None)
    return result


def build_evidence(org_id, db, period, event_types=None) -> dict:
    from src.models.survey import SurveyInstance, SurveyOccurrence

    resolved = resolve_period(period)
    query = db.query(SurveyInstance).filter(
        SurveyInstance.organization_id == org_id, SurveyInstance.status == 'submitted',
        SurveyInstance.submitted_at.isnot(None))
    if event_types:
        query = query.join(SurveyOccurrence).filter(SurveyOccurrence.event_type.in_(event_types))
    if resolved.get('start_date'):
        local_zone = ZoneInfo(TIMEZONE)
        start = datetime.combine(date.fromisoformat(resolved['start_date']), time.min, local_zone)
        stop = datetime.combine(date.fromisoformat(resolved['end_date']) + timedelta(days=1), time.min, local_zone)
        query = query.filter(SurveyInstance.submitted_at >= start.astimezone(timezone.utc),
                             SurveyInstance.submitted_at < stop.astimezone(timezone.utc))
    rows = query.order_by(SurveyInstance.submitted_at.desc(), SurveyInstance.id).limit(MAX_SURVEYS + 1).all()
    if len(rows) > MAX_SURVEYS:
        raise ValueError('This period has more submitted surveys than Ask Genius can safely read at once. Choose a shorter period.')
    records = [original_record(row) for row in rows]
    return {'surveys': records, 'survey_calculated': calculated(records),
            'survey_event_types': list(event_types or []),
            'survey_coverage_note': 'Finalized survey submissions only, with each questionnaire type identified. Periods use survey submission time in the community timezone; event occurrence time is separate. Each submission is counted once. Issue resolution totals cover maintenance only. Saved survey analysis has not been generated.'}


def source(record: dict, excerpt: str | None = None, topic: str | None = None,
           question_id: str | None = None) -> dict:
    if question_id is not None and not any(q['id'] == question_id for q in record['questions']):
        raise ValueError('Unknown survey question')
    def matches(q):
        return any(isinstance(q.get(key), str) and excerpt in q[key]
                   for key in ('answer', 'answer_label'))
    if excerpt is not None and not any(matches(q) for q in record['questions']):
        raise ValueError('Survey excerpt does not match an original submitted answer')
    if question_id is not None and excerpt is not None and not any(
            q['id'] == question_id and matches(q)
            for q in record['questions']):
        raise ValueError('Survey excerpt does not match the selected question')
    return {'source': 'survey', 'survey_id': record['survey_id'], 'kind': 'survey',
            'topic': topic, 'question_id': question_id,
            'label': excerpt or 'View original survey answers', 'excerpt': excerpt,
            'excerpt_truncated': False, 'href': f"/surveys/{record['survey_id']}", 'survey': record}


def explicit_resolution(question: str) -> str | None:
    lowered = question.casefold()
    if re.search(r'\bnot (?:fully )?resolved\b', lowered):
        return None  # Partial and unknown states must not be silently conflated.
    for pattern, value in [(r'\bunresolved\b', 'unresolved'),
                           (r'\bpartially resolved\b', 'partially_resolved'),
                           (r"\b(?:not_checked|not checked|haven[’']t checked(?: yet)?|have not checked(?: yet)?)\b", 'not_checked'),
                           (r'\b(?:fully )?resolved\b', 'resolved')]:
        if re.search(pattern, lowered):
            return value
    return None


def maintenance_only(evidence):
    if evidence.get('survey_resolution_filter'):
        return True
    types = set(evidence.get('survey_event_types', [])) or {
        r.get('event_type', 'maintenance_completed') for r in evidence.get('surveys', [])}
    return types == {'maintenance_completed'}


def filter_resolution(evidence: dict, question: str) -> dict:
    """Bind explicit resolution questions to verified answer values before generation."""
    value = positive_resolution(question)
    if evidence.get('source_scope') != 'surveys' or value is None or not maintenance_only(evidence):
        return evidence
    records = [record for record in evidence['surveys'] if any(
        q['id'] == 'issue_resolution' and q['answer'] == value for q in record['questions'])]
    return {**evidence, 'surveys': records, 'survey_resolution_filter': value,
            'survey_calculated': calculated(records)}


def _simple_request_text(question: str) -> str:
    text = re.sub(r'\s+', ' ', question.casefold()).strip().rstrip('.!? ')
    text = re.sub(r'^(?:please |(?:can|could) you )', '', text)
    # Remove only type selections that the evidence reader actually applied.
    edits = []
    for match, _, exclusion, direct, after_type in _type_selections(text):
        if exclusion:
            edits.append((exclusion.start(), match.end() + (direct.end() if direct else 0)))
        else:
            edits.append((re.search(r'(?:for|from|after)\s*$', text[:match.start()]).start() if after_type else match.start(), match.end()))
    for start, end in reversed(edits):
        text = text[:start] + text[end:]
    text = re.sub(r'\s+', ' ', text).strip()
    return re.sub(r' (?:for|during|in|within) (?:this|the selected) period$', '', text)


def _supported_count(question: str) -> bool:
    text = _simple_request_text(question)
    prefix = r'(?:how many|(?:what is )?(?:the )?(?:count|number) of) '
    unit = r'(?:all )?(?:(?:completed|submitted|maintenance) )*(?:surveys?|submissions?|survey (?:submissions?|responses?)|responses?|(?:distinct |unique )?residents?)'
    completion = r'(?: (?:are there|did we (?:receive|get)|have we received|were received|were submitted|were completed|are completed|are submitted|(?:have )?(?:submitted|completed) (?:a survey|surveys)|responded))?'
    status = r"(?: (?:are|were|report|reported|say|said|show|have)(?: that)?(?: the issue is| the issue was| issues are| issues were)?)? (?:still )?(?:unresolved|(?:fully |partially )?resolved|not_checked|not checked|haven[’']t checked(?: yet)?|have not checked(?: yet)?)"
    return bool(re.fullmatch(prefix + unit + '(?:' + completion + '|' + status + ')', text))


def positive_resolution(question: str) -> str | None:
    """Recognize complete positive requests, never ignore another predicate or negation."""
    value = explicit_resolution(question)
    if value is None:
        return None
    text = _simple_request_text(question)
    state = r"(?:unresolved|(?:fully |partially )?resolved|not_checked|not checked|haven[’']t checked(?: yet)?|have not checked(?: yet)?)"
    unit = r'(?:surveys?|submissions?|residents?)'
    lists = [
        r'which ' + unit + r' (?:say|report|show|are|were)(?: that)?(?: the issue is| the issue was| issues are| issues were)? (?:still )?' + state,
        r'(?:show(?: me)?|list|display|open) (?:the )?(?:all )?' + state + r' (?:maintenance )?' + unit,
        r'(?:show(?: me)?|list|display|open) (?:the )?' + unit + r' (?:with|reporting) (?:still )?' + state + r' issues',
    ]
    narratives = [
        r'what (?:did|do) (?:the )?' + state + ' ' + unit + r' (?:say|report)(?: about (?:maintenance|their maintenance experience|maintenance experience))?',
        r'(?:summarize|explain) (?:the )?' + state + r' (?:maintenance )?' + unit,
    ]
    if _supported_count(question) or any(re.fullmatch(pattern, text) for pattern in [*lists, *narratives]):
        return value
    return None


def local_answer(question: str, evidence: dict, previous_metadata: dict | None = None):
    """Exact list/count/status questions use application records, without model arithmetic."""
    if evidence.get('source_scope') != 'surveys':
        return None
    lowered = question.casefold()
    records = evidence['surveys']
    if re.search(r'\b(?:saved|stored|automatic|classified)\b.{0,35}\b(?:analysis|sentiment|topics?|themes?)\b|\b(?:sentiment|classifications?)\b', lowered):
        return ('Saved survey analysis, topics and sentiment are not available. I can explain the original submitted answers on demand.', [], None)
    original_followup = bool(re.fullmatch(r'(?:please )?(?:show(?: me)?|let me see|open|give me) (?:the |each |all (?:the )?)?(?:original )?(?:answers?|sources?|evidence|surveys?|responses?)(?: behind (?:that|those|this)| for each)?[.!? ]*', lowered))
    prior_ids = (previous_metadata or {}).get('survey_match_ids')
    if original_followup and isinstance(prior_ids, list):
        wanted = set(prior_ids)
        selected = [record for record in records if record['survey_id'] in wanted]
        prior_context = (previous_metadata or {}).get('survey_context', [])
        if prior_context:
            by_id = {record['survey_id']: record for record in selected}
            sources = [source(by_id[item['survey_id']], item.get('excerpt'), item.get('topic'), item.get('question_id'))
                       for item in prior_context if item.get('survey_id') in by_id]
            topics = list(dict.fromkeys(s['topic'] for s in sources if s.get('topic')))
            lines = (previous_metadata or {}).get('survey_topic_lines', {})
            answer = '\n'.join(lines.get(topic, f'- **{topic}:** Supporting survey answers.') for topic in topics) if topics else 'Here are the original questions and submitted answers.'
            return answer, sources, [record['survey_id'] for record in selected]
        return ('Here are the original questions and submitted answers.', [source(record) for record in selected], [record['survey_id'] for record in selected])
    status_filter = positive_resolution(question)
    if status_filter and not maintenance_only(evidence):
        if re.search(r'\bhow many\b|\bcount\b|\bnumber of\b', lowered):
            return ('These survey types ask different questions about unresolved concerns. Specify maintenance surveys for exact issue-resolution counts, or ask me to explain the original answers.', [], None)
        return None
    is_list = bool(re.search(r'\b(?:show|list|which|display|open)\b', lowered))
    is_count = bool(re.search(r'\bhow many\b|\bcount\b|\bnumber of\b', lowered))
    # Narrative and narrower thematic questions use the existing model with original context.
    broad_list = bool(re.fullmatch(r'(?:show(?: me)?|list|display|open) (?:the )?(?:all )?(?:(?:completed|submitted|maintenance) )*(?:surveys?|submissions?)', _simple_request_text(question)))
    if is_count and not _supported_count(question):
        return ('I can calculate exact submission counts, distinct resident counts and counts for each recorded resolution choice. That requested condition has no stored survey classification; I can show or explain the original answers instead.', [], None)
    if re.search(r'\b(?:mention|mentions|mentioning|describe|describes|describing|about|concerning|except|excluding|without|rating|stars?|comments?|faucet|plumbing)\b', _simple_request_text(question)):
        return None
    if not (is_count or is_list and (status_filter or broad_list)):
        return None
    selected = [record for record in records if not status_filter or any(
        q['id'] == 'issue_resolution' and q['answer'] == status_filter for q in record['questions'])]
    reset_cohort = bool(re.search(r'\b(?:all|every) surveys?\b', lowered))
    if not status_filter and not broad_list and not reset_cohort and isinstance(prior_ids, list):
        selected = [record for record in selected if record['survey_id'] in set(prior_ids)]
    resident_count = len({_context(record)['resident_id'] for record in selected})
    suffix = {'unresolved': ' report that the issue is still unresolved',
              'partially_resolved': ' report that the issue is partially resolved',
              'resolved': ' report that the issue is fully resolved',
              'not_checked': ' report that the resident has not checked yet'}.get(status_filter, '')
    if re.search(r'\bresidents?\b', lowered):
        answer = f'{resident_count} unique resident(s){suffix} in {evidence["period"]["label"]}.'
    else:
        kinds = set(evidence.get('survey_event_types', [])) or {r.get('event_type', 'maintenance_completed') for r in selected}
        if status_filter:
            kinds = {'maintenance_completed'}
        label = EVENT_LABELS[next(iter(kinds))].lower() + ' ' if len(kinds) == 1 else ''
        answer = f'{len(selected)} completed {label}survey response(s){suffix} in {evidence["period"]["label"]}.'
    if status_filter:
        answer += ' Ticket completion does not change the resident’s reported resolution status.'
    references = [source(record, topic='Issue resolution' if status_filter else None,
                         question_id='issue_resolution' if status_filter else None) for record in selected]
    if not status_filter and not broad_list and not reset_cohort and (previous_metadata or {}).get('survey_context'):
        by_id = {record['survey_id']: record for record in selected}
        references = [source(by_id[item['survey_id']], item.get('excerpt'), item.get('topic'), item.get('question_id'))
                      for item in previous_metadata['survey_context'] if item.get('survey_id') in by_id]
    # Counts retain their verified cohort internally; the route hides references
    # unless the manager actually requested original evidence.
    return answer, references, [record['survey_id'] for record in selected]
