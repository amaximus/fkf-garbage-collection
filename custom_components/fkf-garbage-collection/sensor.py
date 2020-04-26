import asyncio
from datetime import timedelta
from datetime import datetime
import json
import logging
import lxml.html as lh
import re
import requests
import urllib.request
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

REQUIREMENTS = [ ]

_LOGGER = logging.getLogger(__name__)

CONF_ATTRIBUTION = "Data provided by fkf.hu"
CONF_ZIPCODE = 'zipcode'
CONF_PUBLICPLACE = 'publicplace'
CONF_HOUSENR = 'housenr'
CONF_NAME = 'name'

DEFAULT_NAME = 'FKF Garbage'
DEFAULT_ICON = 'mdi:trash-can-outline'

SCAN_INTERVAL = timedelta(hours=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ZIPCODE): cv.string,
    vol.Required(CONF_PUBLICPLACE): cv.string,
    vol.Required(CONF_HOUSENR): cv.string,
    vol.Optional(CONF_NAME): cv.string,
})

@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    #_LOGGER.debug("start async setup platform")

    name = config.get(CONF_NAME)
    zipcode = config.get(CONF_ZIPCODE)
    publicplace = config.get(CONF_PUBLICPLACE)
    housenr = config.get(CONF_HOUSENR)

    session = async_get_clientsession(hass)

    async_add_devices(
        [FKFGarbageCollectionSensor(name, zipcode, publicplace, housenr)],update_before_add=True)

def dconverter(argument):
    switcher = {
      "Hétfő": "Monday",
      "Kedd": "Tuesday",
      "Szerda": "Wednesday",
      "Csütörtök": "Thursday",
      "Péntek": "Friday",
      "Szombat": "Saturday",
      "Vasárnap": "Sunday"
    }
    return switcher.get(argument)

def gconverter(argument):
    switcher = {
      "Szelektív": "selective",
      "Kommunális": "communal",
      'Szelektív Kommunális': "both",
      'Kommunális Szelektív': "both"
    }
    return switcher.get(argument)

def get_fkfdata(self):
    payload_key = ["district","publicPlace","houseNumber"]
    october_par = ["ajax/publicPlaces","ajax/houseNumbers","ajax/calSearchResults"]
    october_hnd = ["onSelectDistricts","onSavePublicPlace","onSearch"]

    url = 'https://www.fkf.hu/'
    r = requests.get(url)
    cookie=r.headers['Set-Cookie']

    url = 'https://www.fkf.hu/hulladeknaptar'

    payload_val = [self._zipcode, self._publicplace, self._housenr]

    for i in range(len(payload_key)):
       payload = {payload_key[i]: payload_val[i]}
       headers = {'X-OCTOBER-REQUEST-PARTIALS': october_par[i], \
             'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.149 Safari/537.36', \
             'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', \
             'X-OCTOBER-REQUEST-HANDLER': october_hnd[i], \
             'Accept': '*/*', \
             'Sec-Fetch-Dest': 'empty', \
             'X-Requested-With': 'XMLHttpRequest', \
             'Cookie': cookie}
       r = requests.post(url, data=payload, headers=headers)

    fdata = r.json()

    date_format = "%Y.%m.%d"
    today = datetime.today().strftime(date_format)

    s = fdata["ajax/calSearchResults"].replace("\n","").replace("\"","")
    s1 = re.sub("\s{2,}"," ",s)
    s = s1.replace("<div class=communal d-inline-block><i class=fas fa-trash fa-lg mr-2><","") \
          .replace("<div class=selective d-inline-block><i class=fas fa-trash fa-lg><","") \
          .replace("<i class=fas fa-trash fa-lg mr-2><","") \
          .replace("</div>","") \
          .replace("colspan=3><hr class=white m-0","") \
          .replace("/i>","")

    doc = lh.fromstring(s)
    tr_elements = doc.xpath('//tr')

    gday = tr_elements[0].xpath('//td[1]/text()')
    gdate = tr_elements[0].xpath('//td[2]/text()')
    garbage = tr_elements[0].xpath('//td[3]/text()')

    json_data_list = []
    for i in range(len(garbage)-1):
      if garbage[i] and not garbage[i] == ' ':
        a = datetime.strptime(today, date_format)
        b = datetime.strptime(gdate[i], date_format)
        if (b - a).days >= 0: 
          json_data = {"day": dconverter(gday[i]), \
                       "date": gdate[i], \
                       "garbage": gconverter(garbage[i].strip()), \
                       "diff": (b - a).days}
          json_data_list.append(json_data)
    return json_data_list


class FKFGarbageCollectionSensor(Entity):

    def __init__(self, name, zipcode, publicplace, housenr ):
        """Initialize the sensor."""
        self._name = name
        self._zipcode = zipcode
        self._publicplace = publicplace.replace(" ","---")
        self._housenr = housenr
        self._state = None
        self._icon = DEFAULT_ICON

    @property
    def device_state_attributes(self):
        attr = {}

        fkfdata = get_fkfdata(self)

        attr["items"] = len(fkfdata)
        if attr["items"] != 0:
          i = 0
          while i < len(fkfdata):
            attr['in' + str(i)] = fkfdata[i]['diff']
            attr['day' + str(i)] = fkfdata[i]['day']
            attr['date' + str(i)] = fkfdata[i]['date']
            attr['garbage' + str(i)] = fkfdata[i]['garbage']

            i += 1
        return attr

    @asyncio.coroutine
    async def async_update(self):
        _LOGGER.debug("fkf update for " + self._zipcode)
        fkfdata = get_fkfdata(self)

        if len(fkfdata) == 0:
           self._state = None
        else:
           self._state = fkfdata[0]['diff']
        return self._state  

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state
