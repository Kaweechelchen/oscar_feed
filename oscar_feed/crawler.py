import re
from datetime import datetime, timedelta
from pprint import pprint

import pytz
import requests
from bs4 import BeautifulSoup
from dateutil import parser
from ics import Calendar, Event

from . import utils
from .exceptions import OscarFeedLoginException
from .utils import config, log

opt = utils.parse_command_line()


class Shift:
  name: None
  begin: datetime
  end: datetime

  def __init__(self, name: str = None, begin: datetime = None, end: datetime = None):
    if name:
      self.name = name
    if begin:
      self.begin = begin
    if end:
      self.end = end

  def __iter__(self):
    yield 'name', self.name
    yield 'begin', self.begin
    yield 'end', self.end


def login(s: requests.Session):
  log.debug('logging in...')
  login_data = {'username': cfg['user'], 'password': cfg['pass'], 'login': True}
  req = s.post(
    cfg['host'],
    login_data,
  )

  if 'usertext' in req.text:
    log.debug('LOGGED IN 🎉')
    return s

  raise OscarFeedLoginException('wrong credentials in config file, exiting')


def get_shift_ids(s: requests.Session) -> list[int]:
  req = s.get(cfg['host'] + cfg['pages']['shiftlist'])

  soup = BeautifulSoup(req.text, 'html.parser')

  links = soup.find_all('a')
  shift_ids = []
  for link in links:
    href = link.get('href')
    if cfg['pages']['shift'] in href:
      match = re.search(cfg['pages']['shift'] + r"(?P<id>\d+)", href)
      shift_ids.append(int(match.group('id')))

  return shift_ids


def get_shifts(s: requests.Session, ids: list[int]):
  shifts = []
  for id in ids:
    url = cfg['host'] + cfg['pages']['shift'] + str(id)
    log.debug('Getting shift with ID %s @ %s', id, url)
    req = s.get(url)
    soup = BeautifulSoup(req.text, 'html.parser')

    shift_name = soup.find('a', 'navbar-brand').text

    shift_table = soup.table.tbody
    for row in shift_table.find_all('tr'):
      if row.find('th').text:
        log.debug('getting date of row')

        date = pytz.timezone('Europe/Luxembourg').localize(datetime.strptime(row.find('th').text, '%d/%m/%y'))

        time_begin = date
        time_end = date
      for idx, col in enumerate(row.find_all('td')):
        if idx == 0:
          time = re.search(r'(?P<begin_h>\d{2}):(?P<begin_m>\d{2}) - (?P<end_h>\d{2}):(?P<end_m>\d{2})', col.text)
          begin_h = int(time.group('begin_h'))
          begin_m = int(time.group('begin_m'))
          time_begin = time_begin.replace(hour=begin_h, minute=begin_m)

          end_h = int(time.group('end_h'))
          end_m = int(time.group('end_m'))
          if end_h == 0:
            time_end += timedelta(days=1)
          time_end = time_end.replace(hour=end_h, minute=end_m)

        elif col.find('span', 'own-shift'):
          shifts.append(Shift('Perma ' + shift_name, time_begin, time_end))

  return shifts


def get_ics_shifts(feed: dict[str, str]):
  log.debug('Loading data for ICS feed %s', feed['name'])
  text = s.get(feed['url']).text
  text = re.sub(r"<!--(.|\s|\n)*?-->", "", text)
  calendar = Calendar(text)
  shifts = []
  for e in calendar.events:
    e.end = parser.parse(str(e.end)) + timedelta(seconds=1)
    shifts.append(Shift('Perma ' + feed['name'], parser.parse(str(e.begin)), parser.parse(str(e.end))))

  return shifts


def concat_shifts(shifts: list[Shift]):
  shifts = sorted(shifts, key=lambda k: k.begin)

  combined_shifts: list[Shift] = []
  combined_shift: Shift = None
  for shift in shifts:
    if not combined_shift:
      # first iteration
      combined_shift = shift
      continue
    if shift == combined_shift:
      # same shift again
      continue
    if shift.begin >= combined_shift.begin and shift.end <= combined_shift.end:
      continue
    elif combined_shift.end == shift.begin and combined_shift.name == shift.name:
      combined_shift.end = shift.end
    else:
      combined_shifts.append(combined_shift)
      combined_shift = shift

  combined_shifts.append(combined_shift)

  return combined_shifts


def generate_ics(shifts: list[Shift]):
  cal = Calendar()
  for shift in shifts:
    if shift:
      cal.events.add(Event(name=shift.name, begin=shift.begin, end=shift.end))

  with open(config['path_feed'], 'w') as file:
    file.writelines(cal)


cfg = utils.config
s = requests.Session()
s.headers['user-agent'] = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.117 Safari/537.36'


def main():
  utils.set_log_level(opt.verbose)
  log.debug('hello')
  login(s)
  shift_ids = get_shift_ids(s)
  shifts = get_shifts(s, shift_ids)

  if cfg['ics_feeds'] and len(cfg['ics_feeds']):
    for feed in cfg['ics_feeds']:
      try:
        shifts += get_ics_shifts(feed)
      except:
        pass

  shifts = concat_shifts(shifts)
  generate_ics(shifts)
