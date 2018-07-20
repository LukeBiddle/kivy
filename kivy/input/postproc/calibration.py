'''
Calibration
===========

.. versionadded:: 1.9.0

Recalibrate input device to a specific range / offset.

Let's say you have 3 1080p displays, the 2 firsts are multitouch. By default,
both will have mixed touch, the range will conflict with each others: the 0-1
range will goes to 0-5760 px (remember, 3 * 1920 = 5760.)

To fix it, you need to manually reference them. For example::

    [input]
    left = mtdev,/dev/input/event17
    middle = mtdev,/dev/input/event15
    # the right screen is just a display.

Then, you can use the calibration postproc module::

    [postproc:calibration]
    left = xratio=0.3333
    middle = xratio=0.3333,xoffset=0.3333

Now, the touches from the left screen will be within 0-0.3333 range, and the
touches from the middle screen will be within 0.3333-0.6666 range.

'''

__all__ = ('InputPostprocCalibration', )

from kivy.config import Config
from kivy.logger import Logger
from kivy.input import providers
from kivy.input.factory import MotionEventFactory
from kivy.input.motionevent import MotionEvent


class InputPostprocCalibration(object):
    '''Recalibrate the inputs.

    The configuration must go within a section named `postproc:calibration`.
    Within the section, you must have line like::

        devicename = param=value,param=value

    :Parameters:
        `xratio`: float
            Value to multiply X
        `yratio`: float
            Value to multiply Y
        `xoffset`: float
            Value to add to X
        `yoffset`: float
            Value to add to Y

    '''

    def __init__(self):
        super(InputPostprocCalibration, self).__init__()
        self.devices = {}
        self.frame = 0
        self.provider_map = self._get_provider_map()
        if not Config.has_section('postproc:calibration'):
            return
        default_params = {'xoffset': 0, 'yoffset': 0, 'xratio': 1, 'yratio': 1}
        for device_key, params_str in Config.items('postproc:calibration'):
            params = default_params.copy()
            for param in params_str.split(','):
                param = param.strip()
                if not param:
                    continue
                key, value = param.split('=', 1)
                if key not in ('xoffset', 'yoffset', 'xratio', 'yratio'):
                    Logger.error(
                        'Calibration: invalid key provided: {}'.format(key))
                params[key] = float(value)
            self.devices[device_key] = params

    def _get_provider_map(self):
        provider_map = {}
        for input_provider in MotionEventFactory.list():
            p = getattr(providers, input_provider)
            events = []
            for m in p.__all__:
                attr = getattr(p, m)
                if issubclass(attr, MotionEvent):
                    events.append(attr)
            if events:
                provider_map[input_provider] = events
        return provider_map

    def _get_provider_key(self, event):
        for input_type, ev_class in self.provider_map.items():
            key = '({})'.format(input_type)
            for ec in ev_class:
                if isinstance(event, ec) and key in self.devices:
                    return key

    def process(self, events):
        # avoid doing any processing if there is no device to calibrate at all.
        if not self.devices:
            return events

        self.frame += 1
        frame = self.frame
        for etype, event in events:
            # frame-based logic below doesn't account for
            # end events having been already processed
            if etype == 'end':
                continue

            if event.device in self.devices:
                dev = event.device
            else:
                dev = self._get_provider_key(event)
            if not dev:
                continue

            # some providers use the same event to update and end
            if 'calibration:frame' not in event.ud:
                event.ud['calibration:frame'] = frame
            elif event.ud['calibration:frame'] == frame:
                continue
            params = self.devices[dev]
            event.sx = event.sx * params['xratio'] + params['xoffset']
            event.sy = event.sy * params['yratio'] + params['yoffset']
            event.ud['calibration:frame'] = frame
        return events
