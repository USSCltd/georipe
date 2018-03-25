#!/usr/bin/python
import sqlite3
import netaddr
import chardet
import argparse
import sys,os
import itertools


entries = ('ip_begin', 'ip_end', 'inetnum', 'netname', 'descr', 'country', 'notify', 'address', 'phone')
RIPE_DB = os.path.join( os.path.dirname(__file__), 'ripe.db' )

if os.path.isfile(RIPE_DB):
	db = sqlite3.connect(RIPE_DB)
	db.text_factory = str
	sql = db.cursor()
else:
	db = None

items = ['inetnum', 'netname']

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument("-update", dest='update', action="store_true", help='update local database from remote GZ-archive')

arg_parser.add_argument("-ip", dest='ipaddr', action="append", help='search network by IP')
arg_parser.add_argument("-inetnum", dest='inetnum', action="append", help='search network by CIDR (parent)')
arg_parser.add_argument("-inetnums", dest='inetnums', action="append", help='search networks by CIDR (nested)')
arg_parser.add_argument("-netname", dest='netname', action="append", help='search networks by netname')
arg_parser.add_argument("-descr", dest='descr', action="append", help='search networks by descr')
arg_parser.add_argument("-country", dest='country', action="append", help='search networks by country')
arg_parser.add_argument("-notify", dest='notify', action="append", help='search networks by notify')
arg_parser.add_argument("-address", dest='address', action="append", help='search networks by address')
arg_parser.add_argument("-phone", dest='phone', action="append", help='search networks by phone')

arg_parser.add_argument("items", nargs='*', default=['inetnum', 'netname', 'descr', 'country', 'notify', 'address', 'phone'], help="one or more: inetnum,netname,descr,country,notify,address,phone")


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
	import gzip

	DB = "ftp://ftp.ripe.net/ripe/dbase/ripe.db.gz"
	print DB
	resp = urllib2.urlopen(DB)
	size = int( resp.headers.getheader('content-length') or 0 )
	downloaded = 0
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

	print "\nunpacking..."
	with gzip.open(tmpfile.name, 'rb') as gz:
		print 'importing...'
		sql.execute("DROP TABLE IF EXISTS networks")
		sql.execute( 'CREATE TABLE networks(%s)' % ','.join( map(lambda e:"%s INT"%e if e.startswith('ip_') else "%s TEXT"%e, entries) ) )
		#sql.execute( 'CREATE TABLE asns(%s)' % ','.join( map(lambda e:"%s TEXT"%e, entries) ) )
		db.commit()
		nets = {}
		n = 1
		for line in gz:
			for entry in entries:
				if line.startswith(entry):
					if entry == 'inetnum' and nets and nets.get('inetnum'):
						statement = "INSERT INTO networks VALUES(%s)"%','.join( map(lambda e:'?', entries) )
						for i in xrange( len( nets.get('inetnum') ) ):
							sql.execute( statement, map(lambda e:nets.get(e)[i] if type(nets.get(e))==list else nets.get(e), entries) )
						nets = {}
						n += 1
						if n % 25000 == 0:
							db.commit()
							sys.stdout.write("\r%d networks" % n)
							sys.stdout.flush()
					if entry == 'inetnum':
						(ip_from, ip_to) = line[ len(entry)+1: ].strip().split('-')
						nets['inetnum'] = []
						nets['ip_begin'] = []
						nets['ip_end'] = []
						for cidr in netaddr.IPRange( ip_from.strip(), ip_to.strip() ).cidrs():
							nets['inetnum'].append( str(cidr) )
							_min,_max = cidr_to_min_max( str(cidr) )
							nets['ip_begin'].append( _min )
							nets['ip_end'].append( _max )
					else:
						try:
							content = line[ len(entry)+1: ].strip()
							if not content:
								break
							nets[entry] = content
						except:
							codepage = chardet.detect(content)
							try:
								nets[entry] = content.decode( codepage.get('encoding') )
							except Exception as e:
								pass
		sql.execute("CREATE INDEX ip_begin_index ON networks(ip_begin)")
		sql.execute("CREATE INDEX ip_end_index ON networks(ip_end)")
		sql.execute("CREATE INDEX inetnum_index ON networks(inetnum)")
		db.commit()
		sys.stdout.write("\r%d networks\n" % n)
		sys.stdout.flush()

def do_search(items, params):
	statement = []
	args = []
	for attr,val in params.items():
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
		else:
			statement.append( "(%s LIKE ?)" % attr )
			args.append( val )

	results = []
	query = ( "SELECT %s FROM networks WHERE " % ','.join(items) ) + ' AND '.join(statement)
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

def ripe_search(args):
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


def get_stat(netblocks, items):
	statistics = {}
	for item in items:
		if item == 'inetnum':
			ips = set()
			for network in map( lambda n: n.get('inetnum'), netblocks ):
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
		try:
			row.append( values[i] + " " * ( margins[i] - len( values[i].decode('utf-8') ) ) )
		except:
			row.append( values[i] + " " * ( margins[i] - len( values[i] ) ) )
	print ' | '.join(row)


def main( argv=["-h"] ):
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
		if args.inetnum:
			params['inetnum'] = args.inetnum
		if args.inetnums:
			params['inetnums'] = args.inetnums
		if args.netname:
			params['netname'] = args.netname
		if args.descr:
			params['descr'] = args.descr
		if args.country:
			params['country'] = args.country
		if args.notify:
			params['notify'] = args.notify
		if args.address:
			params['address'] = args.address
		if args.phone:
			params['phone'] = args.phone
		if params:
			if db:
				netblocks = ripe_search( params )
			else:
				print "update database first"
				return

	if netblocks:
		summary = get_stat(netblocks, items)
		try:
			margins = map( lambda i: max( map( lambda n: len(str(n.get(i) or '').decode('utf-8')), netblocks ) + [len(i), len(summary[i])] ), items )
		except:
			margins = map( lambda i: max( map( lambda n: len(str(n.get(i) or '')), netblocks ) + [len(i), len(summary[i])] ), items )
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