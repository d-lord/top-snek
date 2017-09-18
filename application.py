#!/usr/bin/env python3

from flask import Flask, request, jsonify
from flask.views import MethodView
import json.decoder
import sqlalchemy
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from pytz import timezone
from marshmallow import Schema, fields, pprint
import config
import ipdb

application = Flask(__name__)

db_engine = sqlalchemy.create_engine(config.db_file)
Session = sessionmaker(bind=db_engine)

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    # SQLAlchemy schema
    id = sqlalchemy.Column(sqlalchemy.String, primary_key=True)
    name = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    story_count = sqlalchemy.Column(sqlalchemy.Integer, default=0)
    last_story = sqlalchemy.Column(sqlalchemy.DateTime, default=None)

    # marshmallow schema
    # TODO: required attrs? or let sqlalchemy enforce that?
    # also, can we make this class static somehow? save User.Schema()
    class Schema(Schema):
        name = fields.Str()
        id = fields.Str()
        story_count = fields.Int()
        last_story = fields.DateTime()

    def __repr__(self):
        return str(self.Schema().dump(self).data)


# TODO: middleware to ensure valid team token
class Leaderboard(MethodView):
    def get(self):
        session = Session()
        schema = User.Schema()
        return jsonify([schema.dump(user).data for user in session.query(User).order_by(User.story_count.desc()).all()])

# a Flask endpoint (distinct from, but corresponding to, the sqlalchemy User)
# TODO: ensure valid administrator is making the request (middleware?)
class APIUser(MethodView):
    def post(self):
        try:
            session = Session()
            result = User.Schema(strict=True).load(request.get_json(force=True))
            # check for error
            if len(result.errors):
                return (jsonify(result.errors), 400)
            new_user = User(**result.data)
            session.add(new_user) 
            # test exists for simpler error message? otherwise it's "(sqlite3.IntegrityError) UNIQUE constraint failed: users.id"
            session.commit()
        except (sqlalchemy.exc.IntegrityError, sqlalchemy.exc.InvalidRequestError) as e:
            return (e.args[0], 400)
        return (b'', 201)
    # maybe it should have PUT etc too. any way of hooking up CRUD via sqlalchemy & marshmallow?
    # it needs /something/ for "told_story", maybe "/users/<id>/told_story"


class CreateDummyData(MethodView):
    def post(self):
        session = Session()
        created, skipped = 0, 0
        for raw_user in config.sample_users:
            new_user = User(**raw_user)
            query = session.query(User).filter(User.id == new_user.id)
            if session.query(query.exists()).scalar():
                skipped += 1
            else:
                session.add(new_user)
                created += 1
        session.commit()
        return (jsonify({"created": created, "skipped": skipped}), 200)


application.add_url_rule('/', view_func=Leaderboard.as_view('leaderboard'))
application.add_url_rule('/users', view_func=APIUser.as_view('users'))
application.add_url_rule('/create_dummy_data', view_func=CreateDummyData.as_view('create'))

if __name__ == '__main__':
    # ipdb.set_trace()
    Base.metadata.create_all(db_engine)
    application.run(port=9443, debug=False)
