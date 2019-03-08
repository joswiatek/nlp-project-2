from flask import current_app as app
from flask import Blueprint
import OSS.models as models

api = Blueprint('api', __name__)

@api.route('/', methods=['GET'])
def index():
    return 'This is the API for Open Source Shakespeare (OSS).'


@api.route('/play/<string:name>', methods=['GET'])
def get_play(name):
    output = 'Test'
    play = models.Works.query.filter_by(workid=name).first()
    print('Output: {}'.format(play))
    return str(play)


@api.route('/play/raw/<string:name>', methods=['GET'])
def get_play_raw(name):
    return "Get play raw stub"
