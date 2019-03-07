"""
The main driver of the application.

This file is called upon launch of the application.  It sets up the
blueprints of the various parts of the site, prepares the config file,
sets up logging, converts all files to be ready for the web (like
scss to css), hosts the server, and sets up general sitewide routes
like the 404 page.  This was set up in this way so that the whole
project can be installed as a python application instead of simply
called on some entrance.
"""


from flask import Flask

import logging
from os import environ
from logging.handlers import RotatingFileHandler

from .views.api import api

def create_app(config_name):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_pyfile('default_config.py')
    app.config.from_pyfile('application.py', silent=True)
    mode = app.config.get('MODE', 'DEV')

    app.register_blueprint(api)

    import OSS.views

    return app


app = create_app(__name__)

formatter = logging.Formatter(
    "[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s")

handler = RotatingFileHandler(app.config.get('LOG_FILENAME',
                                             'OSS.log'),
                              maxBytes=10000000,
                              backupCount=5)

handler.setFormatter(formatter)
app.logger.addHandler(handler)

if not app.debug:
    app.logger.setLevel(app.config.get('LOG_LEVEL', logging.WARNING))
    assert app.config['SERVER_NAME']
else:
    app.logger.setLevel(app.config.get('LOG_LEVEL', logging.DEBUG))
