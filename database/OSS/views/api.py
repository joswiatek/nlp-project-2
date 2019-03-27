from flask import current_app as app
from flask import Blueprint, url_for
from collections import OrderedDict
import OSS.models as models
import pprint
import json
import ast

api = Blueprint('api', __name__)

@api.route('/', methods=['GET'])
def index():
    return 'This is the API for Open Source Shakespeare (OSS).'


@api.route('/play/<string:name>/characters', methods=['GET'])
def get_play_characters(name):
    play = get_play(name)
    characters = get_characters(name)
    return json.dumps(characters)


@api.route('/play/raw/<string:name>', methods=['GET'])
def get_play_raw(name):
    play = get_play(name)
    chapters = get_chapters(play)
    paragraphs = get_paragraphs(play, chapters)
    text = list(map(clean_text, iter(paragraphs)))
    plaintext = [line for (character, line) in text]
    return json.dumps(plaintext)


@api.route('/play/<string:name>', methods=['GET'])
def get_play_with_characters(name):
    play = get_play(name)
    chapters = get_chapters(play)
    paragraphs = get_paragraphs(play, chapters)
    text = list(map(clean_text, iter(paragraphs)))
    return json.dumps(text)


@api.route('/play/modern/<string:name>', methods=['GET'])
def get_play_modern(name):
    return json.dumps(get_modern_play(name))


def get_play(name):
    return models.Works.query.filter_by(workid=name).first()


def get_chapters(play):
    chapter_query = models.Chapters.query
    chapter_query = chapter_query.filter_by(workid=play.workid)
    chapter_query = chapter_query.order_by(models.Chapters.section,
                                           models.Chapters.chapter)
    return chapter_query.all()


def get_modern_play(name):
    output = []
    with open('OSS/static/modern/{}.txt'.format(name), 'r') as f:
        lines = ast.literal_eval(f.read())
        print(lines)
        for item in lines:
            print(item)
            output.append((item[0], item[1]))
    return output


def get_paragraphs(play, chapters):
    paragraphs = []

    for chapter in chapters:
        query = models.Paragraphs.query
        query = query.filter_by(workid=play.workid,
                                section=chapter.section,
                                chapter=chapter.chapter)
        query = query.order_by(models.Paragraphs.section,
                               models.Paragraphs.chapter,
                               models.Paragraphs.paragraphnum)
        chapter_paragraphs = query.all()
        paragraphs += chapter_paragraphs

    return paragraphs


def get_characters(play):
    search = '%{}%'.format(play)
    query = models.Characters.query
    query = query.with_entities(models.Characters.charname,
                                models.Characters.description)
    query = query.filter(models.Characters.works.like(search))
    results = query.all()
    print(results)
    return results


def clean_text(paragraph, modern=False):
    character_query = models.Characters.query
    character_query = character_query.filter_by(charid=paragraph.charid)
    character_name = character_query.first().charname
    line = paragraph.moderntext if modern else paragraph.plaintext
    if line:
        line = line.replace('\n', '')
        line = line.replace('[p]', ' ')
    return (character_name, line)
