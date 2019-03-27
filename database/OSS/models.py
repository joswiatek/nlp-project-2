"""
This file describes the different models in the database for SQLAlchemy.
Each individual model is given a class with various attributes and
a constructor to build said class.  This is used for defining the
schema of the database when quries are made to the database.
"""

from OSS import db

class Characters(db.Model):
    charid = db.Column(db.String(50), primary_key=True)
    charname = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return self.charname


class Works(db.Model):
    workid = db.Column(db.String(50), primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    longtitle = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return self.title


class Chapters(db.Model):
    chapterid = db.Column(db.Integer, primary_key=True)
    workid = db.Column(db.String(50), db.ForeignKey('works.workid'), nullable=False)
    section = db.Column(db.Integer, nullable=False)
    chapter = db.Column(db.Integer, nullable=False)

    def __repr__(self):
        return "{}: {}-{}".format(self.workid, self.section, self.chapter)

class Paragraphs(db.Model):
    paragraphid = db.Column(db.Integer, primary_key=True)
    paragraphnum = db.Column(db.Integer, nullable=False)
    workid = db.Column(db.String(50), db.ForeignKey('works.workid'), nullable=False)
    charid = db.Column(db.String(50), db.ForeignKey('Characters.charid'), nullable=False)
    section = db.Column(db.Integer, nullable=False)
    chapter = db.Column(db.Integer, nullable=False)
    plaintext = db.Column(db.Text, nullable=False)
    moderntext = db.Column(db.Text)

    def __repr__(self):
        return self.plaintext
