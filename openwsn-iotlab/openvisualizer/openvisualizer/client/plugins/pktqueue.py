from __future__ import print_function

import json
import logging
import sys
from collections import deque

from openvisualizer.client.plugins.plugin import Plugin
from openvisualizer.client.view import View
from openvisualizer.motehandler.motestate.motestate import MoteState


@Plugin.record_view("pktqueue")
class Schedule(View):
    COLOR_LINE_MARGIN = 15
    COLOR_HDR_MARGIN = 7.5

    def __init__(self, proxy, mote_id, refresh_rate):
        super(PktQueue, self).__init__(proxy, mote_id, refresh_rate)

        self.title = 'pktqueue'

    def render(self, ms=None):
        yb = self.term.bold_yellow
        n = self.term.normal

        columns = []
        columns += ['|' + yb + '  Type  ' + n]
        columns += ['|' + yb + ' S ' + n]
        columns += ['|' + yb + ' Creator ' + n]
        columns += ['|' + yb + ' Owner ' + n]
        columns += ['|' + yb + ' Addr ' + n + '|']

        header = ''.join(columns)
        hdr_line = ''.join(['-'] * (len(header) - len(columns) * self.COLOR_LINE_MARGIN))

        super(PktQueue, self).render()
        pktqueue_rows = json.loads(ms[MoteState.ST_QUEUE])

        active_rows = []

        for row in queue_rows:
            if row['creator'] != '0':
                    active_rows.append(row)

        #active_rows.sort(key=lambda x: x['slotOffset'])

        w = int(self.term.width / 2)

        print(hdr_line.rjust(abs(w + int(len(hdr_line) / 2))))
        print(header.rjust(abs(w + int(len(header) / 2) + int(ceil(len(columns) * self.COLOR_HDR_MARGIN)))))
        print(hdr_line.rjust(abs(w + int(len(hdr_line) / 2))))

        for r in active_rows:
            c, shift = self._get_row_color(str(r['creator'])[2:])
            # r_str = '|{}{:^8s}{}|{:^3s}|{:^3s}|{:^6s}|{:^8s}|{:^6s}|{:^14s}|{:^5s}|{:^9s}|{:^5s}|'.format(
            r_str = '|{}{:^8s}|{:^6s}|{:^14s}|'.format(
                c, str(
                str(r['creator']),
                str(r['owner']),
                str(r['addr']))
            )

        print('\n')
        

    def run(self):
        logging.debug("Enabling blessed fullscreen")
        with self.term.fullscreen(), self.term.cbreak(), self.term.hidden_cursor():
            super(Schedule, self).run()
        logging.debug("Exiting blessed fullscreen")

    def _get_row_color(self, cell_type):
        if '(TXRX)' == cell_type:
            return self.term.purple, 12
        elif '(TX)' == cell_type:
            return self.term.blue, 6
        else:
            return self.term.red, 6
