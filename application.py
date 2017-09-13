#!/usr/bin/env python3

from flask import Flask, request
from flask_restful import Resource, Api, reqparse, marshal, fields
from json import dumps
import sqlalchemy
from sqlalchemy import create_engine, Column#, Integer, String, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import config
import ipdb

application = Flask(__name__)
api = Api(application)

request_parser = reqparse.RequestParser()
request_parser.add_argument('id', help="Slack user ID", required=True)
request_parser.add_argument('name', help="Slack username (mutable)", required=True)
request_parser.add_argument('story_count', type=int, default=0, help="# of stories told")
# request_parser.add_argument('story_count', type=Date, default=None, help="# of stories told")

db_engine = create_engine(config.db_file) # eugh... validate ../?
Session = sessionmaker(bind=db_engine)

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    # SQLAlchemy schema
    id = Column(sqlalchemy.String, primary_key=True)
    name = Column(sqlalchemy.String, nullable=False)
    story_count = Column(sqlalchemy.Integer, default=0)
    last_story = Column(sqlalchemy.Date, default=None)

    # Flask-RESTful schema
    resource_fields = {
            'name': fields.String,
            'id': fields.String,
            'story_count': fields.Integer,
            'last_story': fields.DateTime
    }

    def __repr__(self):
        return "<User(name='%s', id='%s', story_count='%d', last_story='%s'" % (self.name, self.id, self.story_count, self.last_story)


# TODO: middleware to ensure valid team token
class Leaderboard(Resource):
    def get(self):
        session = Session()
        return [marshal(user, User.resource_fields) for user in session.query(User).order_by(User.story_count.desc()).all()]

# a Flask resource (distinct from the sqlalchemy User)
class APIUser(Resource):
    # create
    def post(self):
        # TODO: ensure valid administrator is making the request (middleware?)
        try:
            session = Session()
            values = request_parser.parse_args(strict=True)
            new_user = User(name=values["name"], id=values["id"],
                    story_count = values["story_count"])
            ipdb.set_trace()
            session.add(new_user)
            session.commit()
        except (sqlalchemy.exc.IntegrityError, sqlalchemy.exc.InvalidRequestError) as e:
            return (e.args[0], 400)
    # maybe it should have PUT etc too. any way of hooking up CRUD via sqlalchemy?

class CreateDummyData(Resource):
    def post(self):
        session = Session()
        created, skipped = 0, 0
        for user_data in [
                {"name": "dal", "id": "LOLJK", "story_count": 5},
                {"name": "steve", "id": "BIGMAN", "story_count": 4},
                {"name": "jaina", "id": "ICE422", "story_count": 0}]:
            new_user = User(**user_data)
            query = session.query(User).filter(User.id == new_user.id)
            if session.query(query.exists()).scalar():
                skipped += 1
            else:
                session.add(new_user)
                created += 1
        session.commit()
        return ({"created": created, "skipped": skipped}, 200)


api.add_resource(Leaderboard, '/')
api.add_resource(APIUser, '/users')
api.add_resource(CreateDummyData, '/create_dummy_data')

if __name__ == '__main__':
    # ipdb.set_trace()
    Base.metadata.create_all(db_engine)
    application.run(port=9443, debug=False)
