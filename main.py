#!/usr/bin/env python
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

class BaseHandler(webapp.RequestHandler):
    def out(self, msg):
        self.response.out.write(msg)

class Main(BaseHandler):
    def get(self):
        self.redirect('https://webcrontab-hrd.appspot.com')

def main():
    URLS = [
        ('/.*', Main),
    ]
    application = webapp.WSGIApplication(
        URLS,
        debug = False
    )
    run_wsgi_app(application)

if __name__ == '__main__':
    main()
