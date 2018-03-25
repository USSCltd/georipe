### Intro

Very famous tool `whois` don't support searching via fields like a 'inetnum', 'descr' and etc. Also it can not
search information for not full matching (for example netname=telecom).

Many `geoip` tools and libraries provide geographical information by IP but can not provide reverse search - IP by geographical information.

### Installation

`pip install georipe`

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

`geoip -circle '28.80 50.85 20' -resolve-whois -kml > out2.kml`

Note, we use resolve from whois queries, because some networks not managed by RIPE and we dont have their in our ripe database.

The third example. How many network in Pacific Ocean?

`geoip.py -circle oceania.txt -resolve-ripe -kml > oceania.kml`

Next. As we member, we can get full IPv4-ranges by city/country/continent.

`geoip -country 'кипр' network > networks.txt`

Lets try to find cisco devices with vulnerable smartinstall service in country:

`masscan -p 4786 iL networks.txt --open -oG cisco.txt`

For fast searching names and description of potentially affected networks we can use also next command:

`ripe -ip cisco.txt`

### Notes

ripe database source ftp://ftp.ripe.net/ripe/dbase/ripe.db.gz

Note, it is only RIPE-part. It contains mostly Europeans and Asians networks. Networks of another continents (maintained by APNIC,AFRINIC,LACNIC and ARIN) may not full descriptions. However this database contains them network ranges.

geoip database source http://geolite.maxmind.com/download/geoip/database/GeoLite2-City-CSV.zip
