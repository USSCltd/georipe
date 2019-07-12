from distutils.core import setup

setup(
  name = 'georipe',
  packages = ['georipe'],
  version = '1.0.5',
  description = 'reverse WHOIS (ripe,apnic,afrinic,lacnic,arin) and GEOIP (geo2ip, ip2geo) mass searching tool',
  author = 'USSC',
  author_email = 'usscltd@gmail.com',
  url = 'https://github.com/USSCltd/georipe',
  bugtrack_url = 'https://github.com/USSCltd/georipe/issues',
  keywords = ['geoip', 'ripe', 'apnic', 'afrinic', 'lacnic', 'arin', 'whois', 'reverse', 'geo2ip', 'networks', 'recon', 'reconnaissance', 'world'],
  classifiers = [],
  scripts=['bin/geoip', 'bin/rwhois'],
  install_requires=[
    'argparse',
    'netaddr',
    'pykml',
    'lxml',
    'ipwhois',
    'folium'
  ]
)
