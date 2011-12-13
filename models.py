"Models for app"
from google.appengine.ext import db

class Crons(db.Model):
  "Holds crontab, urls, times, etc"
  active   = db.BooleanProperty(default = True)
  created  = db.DateTimeProperty(auto_now_add = True)
  modified = db.DateTimeProperty(auto_now_add = True)
  lastrun  = db.DateTimeProperty()
  owner    = db.UserProperty(auto_current_user_add = True)
  name     = db.StringProperty()
  url      = db.StringProperty()
  minutes  = db.ListProperty(int)
  hours    = db.ListProperty(int)
  weekdays = db.ListProperty(int)
  method   = db.StringProperty(default = 'GET')
  payload  = db.StringProperty(default = '')
  response_email = db.BooleanProperty(default = False)
  response_post  = db.StringProperty(default = '')
