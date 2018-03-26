from distutils.core import setup

setup(
  name = 'georipe',
  packages = ['georipe'],
  version = '1.0.2',
  description = 'RIPE and GEOIP mass searching reconnaissance tool',
  author = 'USSC',
  author_email = 'usscltd@gmail.com',
  url = 'https://github.com/USSCltd/georipe',
  bugtrack_url = 'https://github.com/USSCltd/georipe/issues',
  keywords = ['geoip', 'ripe', 'whois', 'networks', 'recon', 'reconnaissance', 'world'],
  classifiers = [],
  scripts=['bin/geoip', 'bin/ripe'],
  install_requires=[
    'argparse',
    'netaddr',
    'pykml',
    'lxml',
    'ipwhois',
    'chardet'
  ]
)
