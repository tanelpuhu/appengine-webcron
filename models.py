from google.appengine.ext import db

class Crons(db.Model):
  active   = db.BooleanProperty(default=True)
  created  = db.DateTimeProperty(auto_now_add=True)
  modified = db.DateTimeProperty(auto_now_add=True)
  lastrun  = db.DateTimeProperty()
  owner    = db.UserProperty(auto_current_user_add=True)
  name     = db.StringProperty()
  url      = db.StringProperty()
  minutes  = db.ListProperty(int)
  hours    = db.ListProperty(int)
  weekdays = db.ListProperty(int)
  method   = db.StringProperty(default = 'GET')
  payload  = db.StringProperty(default = '')
