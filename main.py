#!/usr/bin/env python
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from google.appengine.ext import db
from google.appengine.api.labs import taskqueue
from google.appengine.api.app_identity import get_application_id
from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.api import urlfetch
from google.appengine.api import mail
from models import Crons
import logging
import time
import os

EMAIL_FROM = 'webcron <cron@%s.appspotmail.com>'

ALLMINUTES = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55]

DAYS  = [
    (0, "monday"),
    (1, "tuesday"),
    (2, "wednesday"),
    (3, "thursday"),
    (4, "friday"),
    (5, "saturday"),
    (6, "sunday")
]

MONTHS = [
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december"
]

def get_all_crons():
    "latest 100 crons"
    result = memcache.get('all_crons')
    if not result:
        result = Crons().all().order('-created').fetch(1000)
        memcache.set('all_crons', result)
    return result

def get_active_crons():
    result = memcache.get('active_crons', None)
    if not result:
        result = Crons.all().filter('active =', True)
        memcache.set('active_crons', result)
    return result

def made_changes():
    memcache.delete('all_crons')
    memcache.delete('active_crons')

def to_int_list(list, allowed = None):
    if list:
        result = map(int, list)
        if allowed is not None:
            checked_result = []
            for tmp in result:
                if tmp in allowed:
                    checked_result.append(tmp)
            result = checked_result
        return result
    return []

def get_cron_by_id(id):
    if id is None:
        return None
    try:
        id = int(id)
    except:
        return None
    return Crons().get_by_id(id)

class BaseHandler(webapp.RequestHandler):
    def out(self, msg):
        self.response.out.write(msg)

    def render(self, view, data = None):
        if data is None:
            data = {}
        extra = {
         'allminutes': ALLMINUTES,
           'allhours': range(0, 24),
        'allweekdays': DAYS,
                'now': db.DateTimeProperty.now(),
              'users': users,
        }
        data.update(extra)
        path = os.path.join(
                os.path.dirname(__file__),
                'views',
                '%s.html' % view
        )
        self.out(template.render(path, data))

class Main(BaseHandler):
    def get(self):
        self.render('main', {
            'rows' : get_all_crons()
        })

class Add(BaseHandler):
    def get(self, id = None):
        self.render('edit', {
            'id' : id,
            'current' : get_cron_by_id(id)
        })

    def post(self, id = None):
        cron = None
        if id:
            cron = get_cron_by_id(id)
        if not cron:
            cron = Crons()

        min_list = to_int_list(self.request.get_all('minutes'), ALLMINUTES)
        hour_list = to_int_list(self.request.get_all('hours'))
        week_list = to_int_list(self.request.get_all('weekdays'))

        if 0 in [len(min_list), len(hour_list), len(week_list)]:
            cron.active = False

        cron.name = self.request.get('name')
        cron.url    = self.request.get('url')
        cron.minutes = min_list
        cron.hours = hour_list
        cron.weekdays = week_list
        cron.method = self.request.get('method')
        if cron.method not in ['GET', 'POST']:
            cron.method = 'GET'
        if cron.method == 'GET':
            cron.payload = ''
        else:
            cron.payload = self.request.get('payload') or ''

        cron.response_post = self.request.get('response_post') or ''
        cron.response_email = self.request.get('response_email', '') != ''

        cron.save()
        made_changes()
        id = cron.key().id()
        if id:
            self.redirect('/saved/%d' % id)
            return
        self.redirect('/')

class Delete(BaseHandler):
    def get(self, id = None):
        if id:
            cron = get_cron_by_id(id)
            if cron:
                cron.delete()
                made_changes()
        self.redirect('/')

class Toggle(BaseHandler):
    def get(self, id = None):
        if id:
            cron = get_cron_by_id(id)
            if cron:
                cron.active = cron.active == False
                cron.save()
                made_changes()
        self.redirect('/')

class Run(BaseHandler):
    def add(self, id):
        taskqueue.add(
            url = '/run',
            params = { 'id' : id },
            queue_name ='cron'
        )

    def fetch(self, url, method, payload):
            if method != 'POST':
                payload = None

            return urlfetch.fetch(
                                url,
                                deadline = 10,
                                method = method,
                                payload = payload
            )

    def get(self, id = None):
        if id is None:
            year,mon,mday,hour,min,sec,wday,yday,isdst = time.localtime()
            if min not in ALLMINUTES:
                return
            active_crons = get_active_crons()
            res = active_crons.\
                        filter('minutes IN',  [min]).\
                        filter('hours IN',    [hour]).\
                        filter('weekdays IN', [wday])
            for r in res.fetch(1000):
                self.add(r.key().id())
            return
        self.add(id)
        if self.request.referer:
            self.redirect(self.request.referer)

    def post(self):
        cron = get_cron_by_id(self.request.get('id'))
        if not cron:
            return
        def intransaction():
            run = memcache.get(cron.url)
            if not run:
                logging.info('running %s %s', cron.method, cron.url)
                run = self.fetch(cron.url, cron.method, cron.payload)
                self.send_response_email(run, cron)
                self.send_response_post(run, cron)
                memcache.set(cron.url, 1, time = 30)
                cron.lastrun = db.DateTimeProperty.now()
                cron.save()
                made_changes()

        db.run_in_transaction(intransaction)

    def send_response_post(self, response, cron):
        if not cron.response_post:
            return
        elif response.status_code != 200:
            logging.info('cannot post response (HTTP %s)', response.status_code)
            return
        elif not response.content:
            logging.info('cannot post response (%s)', 'no content')
            return

        logging.info('posting response')
        return urlfetch.fetch(
            cron.response_post,
            deadline = 10,
            method = 'POST',
            payload = response.content
        )

    def send_response_email(self, response, cron):
        if not cron.response_email:
            return
        elif not response.content:
            logging.info('cannot email response (%s)', 'no content')
            return
        sender = EMAIL_FROM % get_application_id()
        logging.info('sending email from %s to %s', sender, cron.owner.email())
        return mail.send_mail(
            sender = sender,
                to = cron.owner.email(),
           subject = "Response to your request (%s)" % cron.name,
              body = "Status: %(status)s\nResponse:\n%(content)s""" % {
                  'content': response.content,
                  'status': response.status_code
              }
        )

def main():
    URLS = [
        ('/run/(?P<id>.*)', Run),
        ('/run', Run),
        ('/add', Add),
        ('/edit/(?P<id>.*)', Add),
        ('/delete/(?P<id>.*)', Delete),
        ('/toggle/(?P<id>.*)', Toggle),
        ('/.*', Main),
    ]
    application = webapp.WSGIApplication(
        URLS,
        debug = False
    )
    run_wsgi_app(application)

if __name__ == '__main__':
    main()
