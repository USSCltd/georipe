#!/usr/bin/python3
import sqlite3
import netaddr
import argparse
import sys,os
import itertools

__version__ = '2.0.1'
entries = ('ip_begin', 'ip_end', 'inetnum', 'netname', 'descr', 'city', 'country', 'notify', 'address', 'phone')
RIR_DB = os.path.join( os.path.dirname(__file__), 'rir.db' )

try:
	db = sqlite3.connect(RIR_DB, check_same_thread=False)
except:
	print("permission denied to open %s" % RIR_DB)
	exit()

db.text_factory = lambda b: b.decode(errors='ignore')
sql = db.cursor()

items = ['inetnum', 'netname']

arg_parser = argparse.ArgumentParser(description="RIR search (ARIN, RIPE, APNIC, LACNIC, AfriNIC)")
arg_parser.add_argument("-update", dest='update', nargs="*", help='update local database from remote GZ-archive')
arg_parser.add_argument("-info", dest='info', action="store_true", help='show total amount netblocks')

arg_parser.add_argument("-ip", dest='ipaddr', action="append", help='search network by IP')
arg_parser.add_argument("-inetnum", dest='inetnum', action="append", help='search network by CIDR (parent)')
arg_parser.add_argument("-inetnums", dest='inetnums', action="append", help='search networks by CIDR (nested)')
arg_parser.add_argument("-netname", dest='netname', action="append", help='search networks by netname')
arg_parser.add_argument("-descr", dest='descr', action="append", help='search networks by descr')
arg_parser.add_argument("-city", dest='city', action="append", help='search networks by city')
arg_parser.add_argument("-country", dest='country', action="append", help='search networks by country')
arg_parser.add_argument("-notify", dest='notify', action="append", help='search networks by notify')
arg_parser.add_argument("-address", dest='address', action="append", help='search networks by address')
arg_parser.add_argument("-phone", dest='phone', action="append", help='search networks by phone')
arg_parser.add_argument("-source", dest='source', action="append", help='search networks by source')

arg_parser.add_argument("-tree", dest='tree', action="store_true", help='show tree of parents networks')
arg_parser.add_argument("-version", dest="version", action="store_true", help="show version")

arg_parser.add_argument("items", nargs='*', default=['inetnum', 'netname', 'descr', 'country', 'notify', 'address', 'phone'], help="one or more: inetnum,netname,descr,city,country,notify,address,phone")

'''
	RIPE: netname, descr, country, notify, address, phone
	AFRINIC: netname, descr, country, notify, address, phone
	APNIC: netname, descr, country
	LACNIC: country, city
	ARIN: descr, notify
'''

def check_db():
	try:
		sql.execute("select 1 from networks limit 1")
		return True
	except:
		sql.execute('CREATE TABLE networks(%s, source TEXT)' % ','.join( list(map(lambda e:"%s INT"%e if e.startswith('ip_') else "%s TEXT"%e, entries)) ))
		return False

def show_db_info():
	for source in ('RIPE', 'AFRINIC', 'APNIC', 'LACNIC', 'ARIN'):
		print(source + ': ', end="")
		count, = sql.execute('SELECT COUNT(inetnum) FROM networks WHERE source=?', (source.lower(),))
		print(count[0])

def cidr_to_min_max(cidr):
	if len( cidr.split('/') ) == 2:
		ip_begin,mask = cidr.split('/')
	else:
		ip_begin = cidr
		mask = 32
	octets = ip_begin.split('.')
	all_octets = []
	for i in range(4):
		i = octets.pop(0) if octets != [] else 0
		all_octets.append(i)
	a,b,c,d = all_octets
	mask = 2**(32-int(mask)) -1
	_min = ( (int(a)<<24) + (int(b)<<16) + (int(c)<<8) + int(d) ) & ~mask
	_max = _min + mask
	return _min,_max


def reset_db(source):
	sql.execute("DELETE FROM networks WHERE source=?", (source,))
	db.commit()


def download(url):
	import urllib.request
	from tempfile import NamedTemporaryFile

	try:
		print(url)
		resp = urllib.request.urlopen(url)
		size = int( resp.headers.get('content-length') or 0 )
		downloaded = 0
		tmpfile = NamedTemporaryFile(delete=False)
		while True:
			data = resp.read(4096)
			if not data:
				break
			tmpfile.write(data)
			downloaded += len(data)
			if size:
				done = int(50 * downloaded / size)
				sys.stdout.write( "\r[%s%s] %d/%d bytes" % ( '=' * done, ' ' * (50-done), downloaded, size ) )
			else:
				sys.stdout.write( "\r%d bytes" % downloaded )
			sys.stdout.flush()
		return tmpfile
	except Exception as e:
		print(str(e))

def parse(tmpfile, key, fields, source):
	import gzip

	print("\nunpacking...")
	fields = ('ip_begin', 'ip_end') + (key,) + fields
	try:
		with gzip.open(tmpfile.name, 'rb') as gz:
			gz._read_eof = lambda :False
			sys.stdout.write('\rimporting...            ')
			sys.stdout.flush()
			nets = {}
			n = 1
			for line in gz:
				line = line.decode(errors='ignore')
				for entry in fields:
					if line.startswith(entry+':'):
						if entry == key:
							if line.find('/') != -1: # 198.148.174.0/24
								cidr = line[ len(entry)+1: ].strip()
								nets['inetnum'] = [cidr]
								nets['ip_begin'] = []
								nets['ip_end'] = []
								_min,_max = cidr_to_min_max(cidr)
								nets['ip_begin'].append(_min)
								nets['ip_end'].append(_max)
							else: # 82.129.219.120 - 82.129.219.127
								(ip_from, ip_to) = line[ len(entry)+1: ].strip().split('-')
								nets['inetnum'] = []
								nets['ip_begin'] = []
								nets['ip_end'] = []
								for cidr in netaddr.IPRange( ip_from.strip(), ip_to.strip() ).cidrs():
									nets['inetnum'].append( str(cidr) )
									_min,_max = cidr_to_min_max( str(cidr) )
									nets['ip_begin'].append( _min )
									nets['ip_end'].append( _max )
						elif nets.get('inetnum'):
							content = line[ len(entry)+1: ].strip()
							if not content:
								break
							if entry in nets:
								nets[entry] += '; ' + content
							else:	
								nets[entry] = content
					elif line.strip() == '' and nets and nets.get('inetnum'):
						if nets.get('netname') != 'NON-RIPE-NCC-MANAGED-ADDRESS-BLOCK':
							statement = "INSERT INTO networks VALUES({values}, '{source}')".format(values=','.join( list(map(lambda e:'?', entries)) ), source=source)
							for i in range( len( nets.get('inetnum') ) ):
								sql.execute( statement, list(map(lambda e:nets.get(e)[i] if type(nets.get(e))==list else nets.get(e,''), entries)) )
							n += 1
							if n % 25000 == 0:
								db.commit()
								sys.stdout.write("\r%d networks" % n)
								sys.stdout.flush()
						nets = {}

		sys.stdout.write("\r%d networks\n" % n)
		sys.stdout.flush()
		db.commit()
		tmpfile.close()

	except Exception as e:
		print(str(e))


def update_ripe():
	'inetnum:        212.140.128.192 - 212.140.128.255'
	with download("ftp://ftp.ripe.net/ripe/dbase/ripe.db.gz") as tmpfile:
		parse(tmpfile, key='inetnum', fields=('netname', 'descr', 'country', 'notify', 'address', 'phone'), source='ripe')
		os.unlink(tmpfile.name)
	
def update_apnic():
	'inetnum:        218.7.99.128 - 218.7.99.159'
	with download("https://ftp.apnic.net/apnic/whois/apnic.db.inetnum.gz") as tmpfile:
		parse(tmpfile, key='inetnum', fields=('netname', 'descr', 'country'), source='apnic')
		os.unlink(tmpfile.name)
	
def update_afrinic():
	'inetnum:        197.254.108.104 - 197.254.108.107'
	with download("https://ftp.afrinic.net/dbase/afrinic.db.gz") as tmpfile:
		parse(tmpfile, key='inetnum', fields=('netname', 'descr', 'country', 'notify', 'address', 'phone'), source='afrinic')
		os.unlink(tmpfile.name)

def update_lacnic():
	'inetnum:    189.108.202.160/29'
	with download("https://ftp.lacnic.net/lacnic/dbase/lacnic.db.gz") as tmpfile:
		parse(tmpfile, key='inetnum', fields=('country', 'city'), source='lacnic')
		os.unlink(tmpfile.name)

def update_arin():
	'route:          198.148.174.0/24'
	with download("https://ftp.arin.net/pub/rr/arin.db.gz") as tmpfile:
		parse(tmpfile, key='route', fields=('descr', 'notify'), source='arin')
		os.unlink(tmpfile.name)
	

def rebuild_indexes():
	sql.execute("DROP INDEX IF EXISTS ip_begin_index")
	sql.execute("DROP INDEX IF EXISTS ip_end_index")
	sql.execute("DROP INDEX IF EXISTS inetnum_index")
	sql.execute("CREATE INDEX ip_begin_index ON networks(ip_begin)")
	sql.execute("CREATE INDEX ip_end_index ON networks(ip_end)")
	sql.execute("CREATE INDEX inetnum_index ON networks(inetnum)")
	db.commit()


def do_search(items, params):
	statement = []
	args = []
	for attr,val in list(params.items()):
		if attr == 'ipaddr':
			ip, ip = cidr_to_min_max(val)
			statement.append( "(inetnum = (SELECT inetnum FROM networks WHERE ? BETWEEN ip_begin AND ip_end ORDER BY ip_begin DESC LIMIT 1) )" )
			args.append( ip )
		elif attr == 'inetnum':
			_min, _max = cidr_to_min_max( val )
			statement.append( "(inetnum = (SELECT inetnum FROM networks WHERE ? BETWEEN ip_begin AND ip_end AND ? BETWEEN ip_begin AND ip_end ORDER BY ip_begin DESC LIMIT 1) )" )
			args.extend( [_min, _max] )
		elif attr == 'inetnums':
			_min, _max = cidr_to_min_max( val )
			statement.append( "(inetnum in (SELECT inetnum FROM networks WHERE ip_begin BETWEEN ? AND ? AND ip_end BETWEEN ? AND ?) )" )
			args.extend( [_min, _max, _min, _max] )
		elif attr.find('no_') != -1:
			statement.append( "(%s NOT LIKE ?)" % attr[3:] )
			args.append( val )
		elif attr.find('_range') != -1:
			_min, _max = val.split('|')
			statement.append( "(inetnum = (SELECT inetnum FROM networks WHERE ? BETWEEN ip_begin AND ip_end AND ? BETWEEN ip_begin AND ip_end ORDER BY ip_begin DESC LIMIT 1) )" )
			args.extend( [_min, _max] )
		else:
			statement.append( "(%s LIKE ?)" % attr )
			args.append( val )

	results = []
	query = ( "SELECT %s FROM networks WHERE " % ','.join(items) ) + ' AND '.join(statement)
	for result in sql.execute( query, args ):
		results.append( dict( list(zip(items,result)) ) )
	return results


def search(items, params):
	results = []
	for attrs in itertools.product( *params.values() ):
		results += do_search( items, dict( list(zip(params.keys(), attrs)) ) )
	return results


def rir_search(args):
	params = {}
	for attr,vals in list(args.items()):
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
						val = input()
						params[attr].append(val)
					except:
						break
				break
			else:
				params[attr].append(val)
	return search(items, params)


def discover_tree(netblocks):
	deep = 0
	while netblocks:
		inetnum = netblocks[0]['inetnum']
		print(" "*deep + inetnum)
		ip_from, ip_to = cidr_to_min_max(inetnum)
		ip_from -= 1
		ip_to += 1
		params = { '_range': [ "%d|%d" % (ip_from, ip_to) ] }
		netblocks = rir_search(params)
		deep += 1


def print_results(netblocks):
	summary = get_stat(netblocks, items)
	margins = list(map( lambda i: max( list(map( lambda n: len(str(n.get(i) or '')), netblocks )) + [len(i), len(summary[i])] ), items ))
	if len(items) > 1:
		print_row( tuple(items), margins )
		print_row( tuple( map( lambda m: '-'*m, margins ) ), margins )
		for netblock in netblocks:
			print_row( list(map( lambda i: str( netblock.get(i) or '' ), items )), margins )
		print_row( tuple( map( lambda m: '-'*m, margins ) ), margins )
		print_row( tuple( map( lambda i: str( summary.get(i) or '' ), items ) ), margins )
	else:
		for netblock in netblocks:
			print_row( list(map( lambda i: str( netblock.get(i) or '' ), items )), [0] )


def get_stat(netblocks, items):
	statistics = {}
	for item in items:
		if item == 'inetnum':
			ips = 0
			for network in [n.get('inetnum') for n in netblocks]:
				_min,_max = cidr_to_min_max(network)
				ips += _max - _min
			statistics[item] = '%d ip' % ips
		else:
			vals = set()
			for val in [str(n.get(item)) or '' for n in netblocks]:
				vals.add(val)
			statistics[item] = '%d %s' % ( len(vals), item )
	return statistics


def print_row( values, margins ):
	row = []
	for i in range( len(values) ):
		row.append( values[i] + " " * ( margins[i] - len( values[i] ) ) )
	print(' | '.join(row))


def main( argv=["-h"] ):
	global items
	args = arg_parser.parse_args(argv)

	items = args.items
	netblocks = []

	if args.version:
		print(__version__)
	elif args.update != None:
		if not args.update:
			args.update = ["afrinic", "lacnic", "apnic", "arin", "ripe"]
		check_db()
		for continent in args.update:
			try:
				update = globals()['update_'+continent.lower()]
				reset_db(continent)
				update()
			except Exception as e:
				print("\n{update} error: {error}".format( update=update.__name__, error=str(e) ))
		rebuild_indexes()
	elif args.info:
		show_db_info()
	else:
		params = {}
		if args.ipaddr:
			params['ipaddr'] = args.ipaddr
		if args.inetnum:
			params['inetnum'] = args.inetnum
		if args.inetnums:
			params['inetnums'] = args.inetnums
		if args.netname:
			params['netname'] = args.netname
		if args.descr:
			params['descr'] = args.descr
		if args.city:
			params['city'] = args.city
		if args.country:
			params['country'] = args.country
		if args.notify:
			params['notify'] = args.notify
		if args.address:
			params['address'] = args.address
		if args.phone:
			params['phone'] = args.phone
		if args.source:
			params['source'] = args.source
		if params:
			if check_db():
				netblocks = rir_search( params )
			else:
				print("please update database")
				return

	if netblocks:
		if args.tree and len(netblocks) == 1:
			discover_tree(netblocks)
		else:
			print_results(netblocks)

	if db:
		db.close()

if __name__ == '__main__':
	main( sys.argv[1:] )
