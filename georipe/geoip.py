#!/usr/bin/python
import csv
import sqlite3
import argparse
import sys,os
import itertools


GEOIP_DB = os.path.join( os.path.dirname(__file__), 'geoip.db' )

if os.path.isfile(GEOIP_DB):
	db = sqlite3.connect(GEOIP_DB)
	db.text_factory = str
	sql = db.cursor()
else:
	db = None

items = ['network']
squares = []
circles = []

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument("-update", dest='update', action="store_true", help='update local database from remote ZIP-archive')

arg_parser.add_argument('-ip', dest="ipaddr", action="append", help='search network by IP')
arg_parser.add_argument('-network', dest="network", action="append", help='search network by CIDR (parent)')
arg_parser.add_argument('-networks', dest="networks", action="append", help='search networks by CIDR (nested)')
arg_parser.add_argument('-asn', dest="asn", action="append", help='search network by ASN')
arg_parser.add_argument('-org', dest="org", action="append", help='search networks by ASN organization')
arg_parser.add_argument('-city', dest="city", action="append", help='search networks in city')
arg_parser.add_argument('-country', dest="country", action="append", help='search networks in country')
arg_parser.add_argument('-continent', dest="continent", action="append", help='search networks on the continent')
arg_parser.add_argument('-square', dest="lat_long_lat_long", action="append", help='search networks in square area')
arg_parser.add_argument('-circle', dest="lat_long_km", action="append", help='search networks in circle area')

arg_parser.add_argument("-kml", dest="save_as_kml", action="store_true", help="save coordinates of netblocks as KML")
arg_parser.add_argument("-resolve-ripe", dest="resolve_ripe", action="store_true", help="ripe db resolve netname (faster)")
arg_parser.add_argument("-resolve-whois", dest="resolve_whois", action="store_true", help="whois resolve netname (slower)")

arg_parser.add_argument("items", nargs='*', default=['network', 'asn', 'org', 'continent', 'country', 'city', 'lat', 'long'], help="one or more: network,asn,org,continent,country,city,lat,long")


def cidr_to_min_max(cidr):
	if len( cidr.split('/') ) == 2:
		ip_begin,mask = cidr.split('/')
	else:
		ip_begin = cidr
		mask = 32
	a,b,c,d = ip_begin.split('.')
	mask = 2**(32-int(mask)) -1
	_min = ( (int(a)<<24) + (int(b)<<16) + (int(c)<<8) + int(d) ) & ~mask
	_max = _min + mask
	return _min,_max

def update(tmpfile):
	import urllib2
	from zipfile import ZipFile
	from io import BytesIO

	DB_ASN = "http://geolite.maxmind.com/download/geoip/database/GeoLite2-ASN-CSV.zip"
	DB_COUNTRY = "http://geolite.maxmind.com/download/geoip/database/GeoLite2-Country-CSV.zip"
	DB_CITY = "http://geolite.maxmind.com/download/geoip/database/GeoLite2-City-CSV.zip"

	def download(uri,target):
		print uri
		resp = urllib2.urlopen(uri)
		size = int( resp.headers.getheader('content-length') or 0 )
		downloaded = 0
		while True:
			data = resp.read(4096)
			if not data:
				break
			target.write(data)
			downloaded += len(data)
			if size:
				done = int(50 * downloaded / size)
				sys.stdout.write( "\r[%s%s] %d/%d bytes" % ( '=' * done, ' ' * (50-done), downloaded, size ) )
			else:
				sys.stdout.write( "\r%d bytes" % downloaded )
			sys.stdout.flush()

	
	download(uri=DB_CITY, target=tmpfile)
	print '\nunpacking...'
	z = ZipFile( tmpfile )
	lang = raw_input("select language (ja/zh-CN/fr/ru/en/pt-BR/de/es): ")
	db_blocks = ''
	db_locations = ''
	for compressed_filepath in z.namelist():
		if compressed_filepath.find('GeoLite2-City-Blocks-IPv4.csv') != -1:
			db_blocks = z.read(compressed_filepath)
		elif compressed_filepath.find('GeoLite2-City-Locations-%s.csv' % lang) != -1:
			db_locations = z.read(compressed_filepath)
	if not db_blocks:
		print "'GeoLite2-City-Blocks-IPv4.csv' not found in %s" % DB_CITY
		return False
	elif not db_locations:
		print "'GeoLite2-City-Locations-%s.csv' not found in %s" % (lang,DB_CITY)
		return False
	z.close()

	print 'importing...'
	sql.execute("DROP TABLE IF EXISTS geoip")
	sql.execute("CREATE TABLE geoip(ip_begin INT, ip_end INT, network TEXT, asn TEXT, org TEXT, continent TEXT, country TEXT, city TEXT, lat FLOAT, long FLOAT)")
	locations = {}
	for location in csv.DictReader( BytesIO(db_locations) ):
		locations.update( { 
			location['geoname_id'] : {
				'continent': location['continent_name'].decode('utf-8').lower(),
				'country': location['country_name'].decode('utf-8').lower(),
				'city': location['city_name'].decode('utf-8').lower()
			}
		} )

	n = 0
	for block in csv.DictReader( BytesIO(db_blocks) ):
		location = locations.get( block['geoname_id'] )
		if location:
			continent = location['continent']
			country = location['country']
			city = location['city']
		else:
			continent = country = city = ''
		#net = netaddr.IPNetwork( block['network'] )  slow!!!
		net = cidr_to_min_max( block['network'] )
		sql.execute(
			"INSERT INTO geoip(ip_begin,ip_end,network,continent,country,city,lat,long) VALUES(?,?,?,?,?,?,?,?)",
			( str(min(net)), str(max(net)), block['network'], continent, country, city, block['latitude'], block['longitude'] )
		)
		if n % 25000 == 0:
			sys.stdout.write("\r%d networks" % n)
			sys.stdout.flush()
		n += 1
	sql.execute("CREATE INDEX ip_begin_index ON geoip(ip_begin)")
	sql.execute("CREATE INDEX ip_end_index on geoip(ip_end)")
	sql.execute("CREATE INDEX network_index ON geoip(network)")
	db.commit()
	sys.stdout.write("\r%d networks\n" % n)
	sys.stdout.flush()

	tmpfile.truncate()
	download(uri=DB_ASN, target=tmpfile)
	z = ZipFile( tmpfile )
	db_asn = ''
	for compressed_filepath in z.namelist():
		if compressed_filepath.find('GeoLite2-ASN-Blocks-IPv4.csv') != -1:
			db_asn = z.read(compressed_filepath)
	if not db_asn:
		print "'GeoLite2-ASN-Blocks-IPv4.csv' not found in %s" % DB_ASN
		return False
	n = 1
	for asn in csv.DictReader( BytesIO(db_asn) ):
		net = asn['network']
		num = asn['autonomous_system_number']
		org = asn['autonomous_system_organization']
		sql.execute( "UPDATE geoip SET asn=?, org=? WHERE network = ?", (num,org,net) )
		if n % 25000 == 0:
			sys.stdout.write("\r%d ASNs" % n)
			sys.stdout.flush()
		n += 1

	db.commit()
	sys.stdout.write("\r%d ASNs\n" % n)
	sys.stdout.flush()
	

def do_search(items, params):
	global squares, circles
	statement = []
	args = []
	def _sign(l):
		l = l.upper()
		for piece,sign in {'N':1, 'S':-1, 'E': 1, 'W': -1}.items():
			if l.find(piece) != -1:
				return float( l.replace(piece,'') ) * sign
		return float(l)
	def _check_square(from_latitude,to_latitude,from_longitude,to_longitude):
		if from_latitude > to_latitude:
			from_latitude,to_latitude = to_latitude,from_latitude
		if from_longitude > to_longitude:
			from_longitude,to_longitude = to_longitude,from_longitude
		return from_latitude,to_latitude,from_longitude,to_longitude

	for attr,val in params.items():
		if attr == 'square':
			(from_latitude,to_latitude,from_longitude,to_longitude) = _check_square( *map( _sign, val.split() ) )
			statement.append( "(lat >= ? AND lat <= ? AND long >= ? AND long <= ?)" )
			args.extend( [from_latitude, to_latitude, from_longitude, to_longitude] )
			squares.append( [from_latitude, to_latitude, from_longitude, to_longitude] )
		elif attr == 'circle':
			lat, lon, radius_km = val.split()
			lat, lon = map( _sign, [lat, lon] )
			radius = float(radius_km) * ( 1.0 / 110.574 )
			#radius = float(radius_km) * ( 1.0 / ( 111.320*math.cos(lat) ) )
			statement.append( "( ( (lat - ?)*(lat - ?) + (long - ?)*(long - ?) ) < ? )" )
			args.extend( [lat, lat, lon, lon, radius*radius] )
			circles.append( [lat, lon, radius] )
		elif attr == 'ipaddr':
			ip, ip = cidr_to_min_max(val)
			statement.append( "(network = (SELECT network FROM geoip WHERE ? BETWEEN ip_begin AND ip_end ORDER BY ip_begin DESC LIMIT 1) )" )
			args.append( ip )
		elif attr == 'network':
			_min, _max = cidr_to_min_max( val )
			statement.append( "(network in (SELECT network FROM geoip WHERE ? BETWEEN ip_begin AND ip_end AND ? BETWEEN ip_begin AND ip_end ORDER BY ip_begin DESC LIMIT 1) )" )
			args.extend( [_min, _max] )
		elif attr == 'networks':
			_min, _max = cidr_to_min_max( val )
			statement.append( "(network in (SELECT network FROM geoip WHERE ip_begin BETWEEN ? AND ? AND ip_end BETWEEN ? AND ?) )" )
			args.extend( [_min, _max, _min, _max] )
		elif attr.find('no_') != -1:
			statement.append( "(%s NOT LIKE ?)" % attr[3:] )
			args.append( val )
		else:
			statement.append( "(%s LIKE ?)" % attr )
			args.append( val )

	results = []
	query = ( "SELECT %s FROM geoip WHERE " % ','.join(items) ) + ' AND '.join(statement)
	#print query
	#print args
	for result in sql.execute( query, args ):
		results.append( dict( zip(items,result) ) )
	return results

def search(items, params):
	results = []
	for attrs in itertools.product( *params.values() ):
		results += do_search( items, dict( zip(params.keys(), attrs) ) )
	return results

def geo_search(args):
	params = {}
	for attr,vals in args.items():
		params[attr] = []
		for val in vals:
			if os.path.isfile(val):
				infile = val
				with open(infile) as f:
					for line in f:
						val = line.split('\n')[0]
						params[attr].append(val)
			elif val == '-':
				while True:
					try:
						val = raw_input()
						params[attr].append(val)
					except:
						break
				break
			else:
				params[attr].append(val)
	return search(items, params)

def resolve_whois(netblocks):
	from ipwhois import IPWhois
	for netblock in netblocks:
		try:
			netname = IPWhois( netblock['network'].split('/')[0] ).lookup_whois()['nets'][0]['name']
			netblock['netname'] = netname[:20]+'..' if len(netname) > 20 else netname
		except:
			pass

def resolve_ripe(netblocks):
	import ripe
	for netblock in netblocks:
		if netblock.get('network'):
			results = ripe.do_search( ["netname"], { "inetnum": netblock['network'] } )
			netname = results[0]['netname'] if results and results[0].get('netname') else ''
			if netname:
				netblock['netname'] = netname[:20]+'..' if len(netname) > 20 else netname

def to_kml(netblocks):
	from pykml.factory import KML_ElementMaker as KML
	from lxml import etree
	import math

	def kml(name, lat,lon):
		return KML.Placemark( 
			KML.name(name),
			KML.Point( 
				KML.coordinates( "%(long).04f,%(lat).04f" % { 'lat': lat, 'long': lon } )
				) 
			) 

	def draw_square(from_latitude, from_longitude, to_latitude, to_longitude):
		return KML.Placemark(
			KML.name('square'),
			KML.Style(
				KML.LineStyle(
					KML.color('ff0000ff'),
					KML.width(2)
				)
			),
			KML.LineString(
				KML.coordinates(
					'%.04f,%.04f,0.0 ' % (from_longitude,from_latitude) +
					'%.04f,%.04f,0.0 ' % (to_longitude,from_latitude) +
					'%.04f,%.04f,0.0 ' % (to_longitude,to_latitude) +
					'%.04f,%.04f,0.0 ' % (from_longitude,to_latitude) +
					'%.04f,%.04f,0.0 ' % (from_longitude,from_latitude)
				)
			)
		)

	def draw_circle(latitude, longitude, radius):
		n = 100
		return KML.Placemark(
			KML.name('circle'),
			KML.Style(
				KML.LineStyle(
					KML.color('ff0000ff'),
					KML.width(2)
				)
			),
			KML.LineString(
				KML.coordinates(
					' '.join( map( lambda xy:'%.04f,%.04f,0.0 '%(xy[0],xy[1]), 
							[ ( longitude+math.cos(2*math.pi/n*x)*radius, latitude+math.sin(2*math.pi/n*x)*radius ) for x in xrange(0,n+1) ]
						)
					)
				)
			)
		)

	points = {}
	places = []
	for netblock in netblocks:
		lat,lon,network,netname = netblock.get('lat'), netblock.get('long'), netblock.get('network'), netblock.get('netname','')
		if lat and lon:
			point = "%s/%s" % (lat, lon)
			if points.get(point):
				points[point].append( ' '.join( [network,netname] ) )
			else:
				points[point] = [network]
	for point in points.keys():
		lat,lon = map( float, point.split("/") )
		places.append( kml( "\n".join( points[point] ), lat, lon ) )
	for square in squares:
		places.append( draw_square( *map( float, square ) ) )
	for circle in circles:
		places.append( draw_circle( *map( float, circle ) ) )
	return etree.tostring( KML.Folder( *tuple(places) ) )

def get_stat(netblocks, items):
	statistics = {}
	for item in items:
		if item == 'network':
			ips = set()
			for network in map( lambda n: n.get('network'), netblocks ):
				_min,_max = cidr_to_min_max(network)
				for ip in xrange( _min, _max ):
					ips.add(ip)
			statistics[item] = '%d ip' % len(ips)
		else:
			vals = set()
			for val in map( lambda n: str(n.get(item)) or '', netblocks ):
				vals.add(val)
			statistics[item] = '%d %s' % ( len(vals), item )
	return statistics

def print_row( values, margins ):
	row = []
	for i in xrange( len(values) ):
		row.append( values[i] + " " * ( margins[i] - len( values[i].decode('utf-8') ) ) )
	print ' | '.join(row)


def main( argv=['-h'] ):
	global items
	args = arg_parser.parse_args(argv)

	items = args.items
	netblocks = []

	if args.update:
		from tempfile import NamedTemporaryFile
		tmpfile = NamedTemporaryFile()
		try:
			update(tmpfile)
		except Exception as e:
			print str(e)
		tmpfile.close()
	else:
		params = {}
		if args.ipaddr:
			params['ipaddr'] = args.ipaddr
		if args.network:
			params['network'] = args.network
		if args.networks:
			params['networks'] = args.networks
		if args.asn:
			params['asn'] = args.asn
		if args.org:
			params['org'] = args.org
		if args.city:
			params['city'] = args.city
		if args.country:
			params['country'] = args.country
		if args.continent:
			params['continent'] = args.continent
		if args.lat_long_lat_long:
			params['square'] = args.lat_long_lat_long
		if args.lat_long_km:
			params['circle'] = args.lat_long_km
		if params:
			if db:
				netblocks = geo_search( params )
			else:
				print "update database first"
				return

	if args.resolve_ripe:
		resolve_ripe( netblocks )
		items.insert(1, "netname")
	elif args.resolve_whois:
		resolve_whois( netblocks )
		items.insert(1, "netname")

	if netblocks and args.save_as_kml:
		print to_kml( netblocks )
	elif netblocks:
		summary = get_stat(netblocks, items)
		margins = map( lambda i: max( map( lambda n: len(str(n.get(i) or '').decode('utf-8')), netblocks ) + [len(i), len(summary[i])] ), items )
		if len(items) > 1:
			print_row( tuple(items), margins )
			print_row( tuple( map( lambda m: '-'*m, margins ) ), margins )
		for netblock in netblocks:
			print_row( map( lambda i: str( netblock.get(i) or '' ), items ), margins )
		if len(items) > 1:
			print_row( tuple( map( lambda m: '-'*m, margins ) ), margins )
			print_row( tuple( map( lambda i: str( summary.get(i) or '' ), items ) ), margins )

	if db:
		db.close()

if __name__ == '__main__':
	main( sys.argv[1:] )