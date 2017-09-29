#!/usr/bin/env python3

from flask import Flask, request, jsonify, abort
from flask.views import MethodView
from flask_sqlalchemy import SQLAlchemy
import json.decoder
import sqlalchemy
# from sqlalchemy.ext.declarative import declarative_base
# from sqlalchemy.orm import sessionmaker
from datetime import datetime
from pytz import timezone
from marshmallow import Schema, fields, pprint
import marshmallow.exceptions
from config import config
import logging

application = Flask(__name__)
application.config['SQLALCHEMY_DATABASE_URI'] = config["db_file"]
application.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = config.get("db_track_modifications", False)

# db_engine = SQLAlchemy.create_engine(config.db_file)
db = SQLAlchemy(application)

logger = logging.getLogger(__name__)

class User(db.Model):
    __tablename__ = 'users'

    # SQLAlchemy schema
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, nullable=False)
    story_count = db.Column(db.Integer, default=0)
    last_story = db.Column(db.DateTime, default=None)

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
        schema = User.Schema()
        return jsonify([schema.dump(user).data for user in db.session.query(User).order_by(User.story_count.desc()).all()])

# a Flask endpoint (distinct from, but corresponding to, the sqlalchemy User)
# TODO: ensure valid administrator is making the request (middleware?)
class UserAPI(MethodView):
    # create a user
    def post(self):
        try:
            result = User.Schema(strict=True).load(request.get_json(force=True))
            # check for error
            if len(result.errors):
                return jsonify(result.errors), 400
            new_user = User(**result.data)
            db.session.add(new_user)
            # test exists for simpler error message? otherwise it's
            #   "(sqlite3.IntegrityError) UNIQUE constraint failed: users.id"
            db.session.commit()
        except (sqlalchemy.exc.IntegrityError, sqlalchemy.exc.InvalidRequestError) as e:
            return jsonify(e.args[0]), 400
        except (marshmallow.exceptions.ValidationError) as e:
            return jsonify({"Invalid POST data": e.args[0]}), 400
        return b'', 201

    # maybe it should have PUT etc too. any way of hooking up CRUD via sqlalchemy & marshmallow?
    # it needs /something/ for "told_story", maybe "/users/<id>/told_story"
    def put(self, user_id):
        ...

    def get(self, user_id):
        schema = User.Schema()
        if user_id is None:
            return jsonify([schema.dump(user).data for user in db.session.query(User).order_by(User.story_count.desc()).all()])
        else:
            result = schema.dump(db.session.query(User).filter_by(id=user_id).first())
            if len(result.data):
                return jsonify(result.data)
            elif len(result.errors):
                logger.warning(result.errors)
                return jsonify(result.errors), 400
            else:
                return b'', 404


class CreateDummyData(MethodView):
    def post(self):
        created, skipped = 0, 0
        for raw_user in config.sample_users:
            new_user = User(**raw_user)
            query = db.session.query(User).filter(User.id == new_user.id)
            if db.session.query(query.exists()).scalar():
                skipped += 1
            else:
                db.session.add(new_user)
                created += 1
        db.session.commit()
        return jsonify({"created": created, "skipped": skipped}), 200


@application.errorhandler(404)
def missing(error):  # different from a view returning 404: this is returned on eg /nonexistent
    if "" in request.headers:
        return super()  # err... default Flask behaviour?
    return b'', 404

application.add_url_rule('/leaderboard', view_func=Leaderboard.as_view('leaderboard'))
application.add_url_rule('/create_dummy_data', view_func=CreateDummyData.as_view('create'))


@application.route('/403')
def make403():
    abort(403, jsonify({"error": "you're a bad"}))


user_view = UserAPI.as_view('users')
application.add_url_rule('/users/', defaults={'user_id': None}, view_func=user_view, methods=['GET'])
application.add_url_rule('/users/', view_func=user_view, methods=['POST'])
application.add_url_rule('/users/<user_id>', view_func=user_view, methods=['GET', 'POST', 'PUT'])


if __name__ == '__main__':
    # ipdb.set_trace()
    db.create_all()
    application.run(port=9443, debug=False,
                    use_reloader=True, reloader_type='watchdog')
