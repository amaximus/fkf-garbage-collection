""" FKF Garbage collection calendar."""

import logging
import re
from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.util import Throttle

from .const import CALENDAR_NAME, CALENDAR_PLATFORM, DOMAIN, SENSOR_PLATFORM

_LOGGER = logging.getLogger(__name__)
MIN_TIME_BETWEEN_UPDATES = timedelta(hours=1)

async def async_setup_platform(
    hass, config, async_add_entities, discovery_info=None
): # pylint: disable=unused-argument
    """Add calendar entities to HA, of there are calendar instances."""
    # Only single instance allowed
    if FKFGarbageCollectionCalendar.instances == 0:
        async_add_entities([FKFGarbageCollectionCalendar(hass)], True)

class FKFGarbageCollectionCalendar(CalendarEntity):
    """The garbage collection calendar class."""

    instances = 0

    def __init__(self, hass):
        """Create empry calendar."""
        self._name = CALENDAR_NAME
        FKFGarbageCollectionCalendar.instances += 1

    @property
    def event(self):
        """Return the next upcoming event."""
        return self.hass.data[DOMAIN][CALENDAR_PLATFORM].event

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    async def async_update(self):
        """Update all calendars."""
        await self.hass.data[DOMAIN][CALENDAR_PLATFORM].async_update()

    async def async_get_events(self, hass, start_date, end_date):
        """Get all events in a specific time frame."""
        return await self.hass.data[DOMAIN][CALENDAR_PLATFORM].async_get_events(
            hass, start_date, end_date
        )

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        if self.hass.data[DOMAIN][CALENDAR_PLATFORM].event is None:
            # No tasks, we don't need to show anything.
            return None
        return {}


class EntitiesCalendarData:
    """Class used by the Entities Calendar class to hold all entity events."""

    def __init__(self, hass):
        """Initialize an Entities Calendar Data."""
        self.event: CalendarEvent | None = None
        self._hass = hass
        self.entities = []
        self._translation = {
            "hu": { "communal": "kommunális",
                    "green": "zöld",
                    "selective": "szelektív"
                  },
            "en": { "communal": "communal",
                    "green": "green",
                    "selective": "selective"
                  }
       }

    def add_entity(self, entity_id):
        """Append entity ID to the calendar."""
        if entity_id not in self.entities:
            self.entities.append(entity_id)

    def remove_entity(self, entity_id):
        """Remove entity ID from the calendar."""
        if entity_id in self.entities:
            self.entities.remove(entity_id)

    def _split_and_translate(self, lng, gstr):
        gtranslated = ""
        garbagelist = gstr.split("_")
        for g in garbagelist:
            gtranslated += self._translation[lng][g] + ","
        gtranslated = gtranslated[:-1]
        return gtranslated

    async def async_get_events(self, hass: HomeAssistant, start_datetime: datetime, end_datetime: datetime) -> list[CalendarEvent]:
        """Get all tasks in a specific time frame."""
        events: list[CalendarEvent] = []
        startdates = {}
        garbages = {}
        calendar_lang = "en"
        friendly_name = ""
        if SENSOR_PLATFORM not in hass.data[DOMAIN]:
            return events
        #start_date = start_datetime.date()
        #end_date = end_datetime.date()
        for entity in self.entities:
            if entity not in hass.data[DOMAIN][SENSOR_PLATFORM]:
                continue
            attributes = self._hass.states.get(entity).attributes
            for key in attributes:
                x = re.search('^date', key)
                if x is not None:
                    idx = key[x.end():]
                    startdates[idx] = datetime.strptime(attributes[key].__str__(), "%Y.%m.%d").date()
                x = re.search('^garbage', key)
                if x is not None:
                    idx = key[x.end():]
                    garbages[idx] = attributes[key]
                if key == 'calendar_lang':
                    calendar_lang = attributes[key]
                if key == 'friendly_name':
                    friendly_name = attributes[key]

            i = 0
            while i < len(startdates):
                if startdates[str(i)] is not None:
                    end = startdates[str(i)] + timedelta(days=1)
                    if calendar_lang in self._translation:
                      gtype = self._split_and_translate(calendar_lang, garbages[str(i)])
                    else:
                      gtype = self._split_and_translate("en", garbages[str(i)])
                    _LOGGER.debug("async_get_events: %s s: %s, e: %s, type: %s", friendly_name, startdates[str(i)].strftime("%Y.%m.%d"), end.strftime("%Y.%m.%d"),gtype)

                    event = {
                        "uid": entity,
                        "summary": friendly_name + ": " + gtype,
                        "start": {"date": startdates[str(i)].strftime("%Y-%m-%d")},
                        "end": {"date": end.strftime("%Y-%m-%d")},
                        "allDay": True,
                    }
                    events.append(event)
                i += 1
        return events

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self) -> None:
        """Get the latest data."""
        next_dates = {}
        garbages = {}
        calendar_lang = "en"
        friendly_name = ""
        #i = 0
        for entity in self.entities:
          if entity not in self._hass.data[DOMAIN][SENSOR_PLATFORM]:
            continue
          if self._hass.states.get(entity) is None:
            continue
          attributes = self._hass.states.get(entity).attributes
          for key in attributes:
            x = re.search('^date', key)
            if x is not None:
              idx = key[x.end():]
              next_dates[str(idx)] = datetime.strptime(attributes[key].__str__(), "%Y.%m.%d").date()

            x = re.search('^garbage', key)
            if x is not None:
              idx = key[x.end():]
              garbages[str(idx)] = attributes[key]

            if key == 'calendar_lang':
              calendar_lang = attributes[key]
            if key == 'friendly_name':
              friendly_name = attributes[key]

        if len(next_dates) > 0:
          idx = min(next_dates.keys(), key=(lambda k: next_dates[k]))
          start = next_dates[str(idx)]
          end = start + timedelta(days=1)
          if calendar_lang in self._translation:
            name = friendly_name + ": " + self._split_and_translate(calendar_lang, garbages[str(idx)])
          else:
            name = friendly_name + ": " + self._split_and_translate("en", garbages[str(idx)])

          _LOGGER.debug("async_update: %s s: %s, e: %s, type: %s", friendly_name, start.strftime("%Y.%m.%d"), end.strftime("%Y.%m.%d"),name)

          self.event = CalendarEvent(
            summary=name,
            start=start,
            end=end,
          )
