import argparse
import logging
import sys
from datetime import datetime
from colored import bg, fg, stylize

import yaml


class ColoredFormatter(logging.Formatter):
  """Colorise the logging output."""

  COLORS = {'ERROR': bg('dark_red_2') + fg('white'),
            'WARNING': fg('yellow'), }

  def format(self,
             record):
    level_name = record.levelname
    record.levelname = record.levelname.ljust(7)
    line = logging.Formatter.format(self, record)

    if level_name in ColoredFormatter.COLORS:
      line = stylize(line, ColoredFormatter.COLORS[level_name])

    return line


log = logging.getLogger(__file__)
log.setLevel(logging.INFO)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = ColoredFormatter('%(levelname)-7s - %(message)s')
ch.setFormatter(formatter)
log.addHandler(ch)

if "pytest" in sys.modules:
  config_file = 'config.sample.yml'
else:
  config_file = 'config.yml'

with open(config_file, 'r') as config_data:
  config = yaml.load(config_data,
                     Loader=yaml.SafeLoader)


def set_log_level(level: int) -> None:
  global log
  if level == 0:
    log.setLevel(logging.WARNING)

  if level == 1:
    log.setLevel(logging.INFO)

  if level >= 3:
    log.setLevel(logging.DEBUG)


def parse_command_line(*args):
  parser = argparse.ArgumentParser(description='OSCAR Feed generator.')
  parser.add_argument('-v', action='count', dest='verbose', default=0,
                      help='Set verbose level. Want moar noise?? use -vvv.')

  if args:
    return parser.parse_args(*args)

  return parser.parse_args()
