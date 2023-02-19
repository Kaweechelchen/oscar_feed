import re
from datetime import datetime, timedelta

import pytz
import requests
from bs4 import BeautifulSoup
from ics import Calendar, Event

from . import utils
from .exceptions import OscarFeedLoginException
from .utils import config, log

opt = utils.parse_command_line()


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
      match = re.search(cfg['pages']['shift'] + '(?P<id>\d+)', href)
      shift_ids.append(int(match.group('id')))

  return shift_ids


def get_shifts(s: requests.Session, ids: list[int]):
  shifts = []
  for id in ids:
    url = cfg['host'] + cfg['pages']['shift'] + str(id)
    log.debug('Getting shift with ID %s @ %s', id, url)
    req = s.get(url)
    shift_table = BeautifulSoup(req.text, 'html.parser').table.tbody
    for row in shift_table.find_all('tr'):
      if row.find('th').text:
        log.debug('getting date of row')

        date = pytz.timezone('Europe/Luxembourg').localize(datetime.strptime(row.find('th').text, '%d/%m/%y'))

        time_start = date
        time_end = date
      for idx, col in enumerate(row.find_all('td')):
        if idx == 0:
          time = re.search('(?P<start_h>\d{2}):(?P<start_m>\d{2}) - (?P<end_h>\d{2}):(?P<end_m>\d{2})', col.text)
          start_h = int(time.group('start_h'))
          start_m = int(time.group('start_m'))
          time_start = time_start.replace(hour=start_h, minute=start_m)

          end_h = int(time.group('end_h'))
          end_m = int(time.group('end_m'))
          if end_h == 0:
            time_end += timedelta(days=1)
          time_end = time_end.replace(hour=end_h, minute=end_m)

        elif col.find('span', 'own-shift'):
          shifts.append({'start': time_start, 'end': time_end})

  shifts = sorted(shifts, key=lambda k: k['start'])

  combined_shifts = []
  combined_shift = None
  for shift in shifts:
    if not combined_shift:
      combined_shift = shift
      continue
    if shift == combined_shift:
      continue
    if shift['start'] >= combined_shift['start'] and shift['end'] <= combined_shift['end']:
      continue
    elif combined_shift['end'] == shift['start']:
      combined_shift['end'] = shift['end']
    else:
      combined_shifts.append(combined_shift)
      combined_shift = shift

  combined_shifts.append(combined_shift)

  return combined_shifts


def generate_ics(shifts: list):
  cal = Calendar()
  for shift in shifts:
    cal.events.add(Event(name='Permanence', begin=shift['start'], end=shift['end']))

  with open(config['path_feed'], 'w') as file:
    file.writelines(cal)


s = requests.Session()
cfg = utils.config


def main():
  utils.set_log_level(opt.verbose)
  log.debug('hello')
  login(s)
  shift_ids = get_shift_ids(s)
  shifts = get_shifts(s, shift_ids)

  generate_ics(shifts)
