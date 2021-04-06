### Intro

Very famous tool `whois` don't support searching via fields like a 'inetnum', 'descr' and etc. Also it can not
search information for not full matching (for example netname=telecom).

Many `geoip` tools and libraries provide geographical information by IP but can not provide reverse search - IP by geographical information.

### Installation

`pip2 install georipe`

### Download RIPE and GEOIP database

`ripe -update`

`geoip -update`

it takes around 600MB and 400MB disk spaces respectively.

### List of available options

`ripe -h`

`geoip -h`

### Usage

So, suppose, we want to find some networks... For example, "The North Atlantic Treaty Organization" (we use '%' as substitution char for more fully searching):

`ripe -netname nato-%`

Next, we can see where this networks are located:

`ripe -netname nato-% inetnum | geoip -networks -`

Also we can import results into KML-file:

`ripe -netname nato-% inetnum | geoip -networks - -kml > nato.kml`

Next example. We try to find some nuclear object through simply query:

`ripe -descr %nuclear% inetnum descr country`

Lets try find all networks around some nuclear station. For example Fukushima (20 kilemeters radius):

`geoip -circle 28.80,50.85,20 -resolve-whois -html out.html`

Note, we use resolve from whois queries, because some networks not managed by RIPE and we dont have their in our ripe database.

The third example. How many network in Pacific Ocean?

`geoip.py -circle oceania.txt -resolve-ripe -kml > oceania.kml`

Next. As we member, we can get full IPv4-ranges by city/country/continent.

`geoip -country 'кипр' network > networks.txt`

Lets try to find cisco devices with vulnerable smartinstall service in country:

`masscan -p 4786 iL networks.txt --open -oG cisco.txt`

For fast searching names and description of potentially affected networks we can use also next command:

`ripe -ip cisco.txt`

### Others

All netblock and network names around the world (2GiB RAM):

`rwhois -inetnums 0.0.0.0/0 inetnum netname`

Sort countries by internet activity (1GiB RAM):

`geoip -networks 0.0.0.0/0 country | sort | uniq -c | sort -n`

`geoip -networks 0.0.0.0/0 city|sort |uniq -c|sort -n |nl`

Sort cities of country by internet activity:

`geoip -country россия city|sort |uniq -c|sort -n`


```
shodan download out port:4786
shodan parse --fields ip_str out.json.gz | geoip -ip -
```

`awk '{print $1}' /var/log/apache2/access.log | sort -u | geoip -ip - network country city`

`cat bind.log | grep queries | awk '{print $6}' | cut -d '#' -f 1 | sort -u | geoip -ip - network country city`

### Notes

ripe database source ftp://ftp.ripe.net/ripe/dbase/ripe.db.gz
apnic database source https://ftp.apnic.net/apnic/whois/apnic.db.inetnum.gz
afrinic database source https://ftp.afrinic.net/dbase/afrinic.db.gz
lacnic database source https://ftp.lacnic.net/lacnic/dbase/lacnic.db.gz
arin database source https://ftp.arin.net/pub/rr/arin.db

geoip database source http://geolite.maxmind.com/download/geoip/database/GeoLite2-City-CSV.zip
