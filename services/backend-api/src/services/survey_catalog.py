"""Seven fixed, approved BoomSay questionnaires; no generated questions."""
from copy import deepcopy
import json
from pathlib import Path

CATALOG = json.loads((Path(__file__).parent / 'data/survey_catalog.json').read_text())
EVENT_LABELS = {
    'move_in_completed': 'Move-in', 'maintenance_completed': 'Maintenance',
    'lease_month_3': '3-month', 'lease_month_6': '6-month',
    'lease_month_9': '9-month renewal planning', 'lease_renewed': 'Lease renewal',
    'move_out_completed': 'Move-out',
}
TEMPLATE_EVENTS = {item['id']: item['event_type'] for item in CATALOG['templates']}


def event_type_for(questionnaire: dict, context: dict) -> str:
    # Old snapshots already identify their immutable maintenance template.
    return questionnaire.get('event_type') or TEMPLATE_EVENTS.get(questionnaire['id']) or context.get('event_type', '')


def bind_questionnaire(context: dict, event_type: str = 'maintenance_completed') -> dict:
    template = next((deepcopy(item) for item in CATALOG['templates'] if item['event_type'] == event_type), None)
    if template is None:
        raise ValueError('Unsupported survey event type; no questionnaire was selected')
    template.update(version=1, catalog_version=CATALOG['catalog_version'],
                    rating_labels=deepcopy(CATALOG['rating_labels']))
    template['title'] = template['title'].format(**context)
    for question in template['questions']:
        question['rendered_text'] = question['text'].format(**context)
    return template


def validate_answers(template: dict, answers: dict, *, final=False) -> dict:
    if not isinstance(answers, dict):
        raise ValueError('Answers must be a question-ID object')
    questions = {q['id']: q for q in template['questions']}
    unknown = set(answers) - set(questions)
    if unknown:
        raise ValueError('Unknown question ID: ' + ', '.join(sorted(unknown)))
    result = {}
    for key, value in answers.items():
        q = questions[key]
        if value is None or value == '':
            result[key] = '' if q['type'] == 'text' else None
        elif q['type'] == 'rating':
            if type(value) is int and 1 <= value <= 5:
                result[key] = value
            elif isinstance(value, str) and value in {x['value'] for x in q.get('special_options', [])}:
                result[key] = value
            else:
                raise ValueError(f'{key}: choose a number from 1 to 5 or a listed special option')
        elif q['type'] == 'single_choice':
            if not isinstance(value, str) or value not in {x['value'] for x in q['options']}:
                raise ValueError(f'{key}: choose a listed option')
            result[key] = value
        elif q['type'] == 'text':
            if not isinstance(value, str) or len(value) > q['max_length']:
                raise ValueError(f"{key}: text must be at most {q['max_length']} characters")
            result[key] = value
        else:
            raise ValueError('Unsupported question type in bound questionnaire')
    if final:
        for q in template['questions']:
            if q['required'] and result.get(q['id']) in (None, ''):
                raise ValueError(f"{q['id']}: an answer is required")
            if not q['required']:
                result.setdefault(q['id'], '')
    return result


def answer_label(question: dict, value, questionnaire: dict):
    if value is None or value == '':
        return None
    if question['type'] == 'rating' and type(value) is int:
        return f"{value} — {questionnaire['rating_labels'][str(value)]}"
    for option in question.get('options', []) + question.get('special_options', []):
        if option['value'] == value:
            return option['label']
    return value
