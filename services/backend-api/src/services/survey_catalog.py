"""The maintenance_v1 questionnaire adapted from BoomSay's fixed catalog."""
from copy import deepcopy
import json
from pathlib import Path

CATALOG = json.loads((Path(__file__).parent / 'data/maintenance_survey_catalog.json').read_text())


def bind_questionnaire(context: dict) -> dict:
    template = deepcopy(CATALOG['templates'][0])
    template.update(version=1, catalog_version=CATALOG['catalog_version'],
                    rating_labels=deepcopy(CATALOG['rating_labels']))
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
