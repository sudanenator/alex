#!/usr/bin/env python
# -*- coding: utf-8 -*-


"""
Generate NLG reply/confirm/apologize/request CrowdFlower tasks for the PTIEN domain.
"""


from __future__ import unicode_literals
from alex.components.slu.da import DialogueAct, DialogueActItem

from argparse import ArgumentParser
import codecs
import re
import sys
import random
import csv

from util import *

# Start IPdb on error in interactive mode
from tgen.debug import exc_info_hook
sys.excepthook = exc_info_hook


STOPS = ['Astor Place',
         'Bleecker Street',
         'Bowery',
         'Bowling Green',
         'Broad Street',
         'Bryant Park',
         'Canal Street',
         'Cathedral Parkway',
         'Central Park',
         'Chambers Street',
         # 'City College',
         'City Hall',
         'Columbia University',
         'Columbus Circle',
         'Cortlandt Street',
         'Delancey Street',
         'Dyckman Street',
         'East Broadway',
         'Essex Street',
         'Franklin Street',
         'Fulton Street',
         'Grand Central',
         'Grand Street',
         # 'Harlem',
         'Herald Square',
         'Houston Street',
         # 'Hudson Yards',
         # 'Hunter College',
         'Inwood',
         # 'Lafayette Street',
         'Lincoln Center',
         'Marble Hill',
         # 'Museum of Natural History',
         # 'New York University',
         'Park Place',
         'Penn Station',
         'Port Authority Bus Terminal',
         'Prince Street',
         'Rector Street',
         'Rockefeller Center',
         'Roosevelt Island',
         # 'Sheridan Square',
         # 'South Ferry',
         # 'Spring Street',
         'Times Square',
         'Union Square',
         'Wall Street',
         'Washington Square',
         'World Trade Center', ]

WORD_FOR_NUMBER = ['zero', 'one', 'two', 'three', 'four', 'five', 'six',
                   'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve']

MINUTE_VALUES = [(0.16, '0:10', 'ten'), (0.25, '0:15', 'fifteen'),
                 (0.33, '0:20', 'twenty'), (0.5, '0:30', 'thirty')]

BUS_LINES = [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 14, 15, 20, 21, 22, 23, 31,
             34, 35, 42, 50, 57, 60, 66, 72, 79, 86, 96, 98, 100, 101, 102,
             103, 104, 106, 116]

ACK_SLOTS_REGEX = '^(from|to|departure_time|arrival_time|time|ampm|vehicle|alternative)'


def word_for_ampm(hour, ampm):
    """Return 'morning', 'afternoon', or 'evening' for the given hour and
    AM/PM setting.
    """
    if ampm == 'am':
        return 'morning'
    if hour < 6:
        return 'afternoon'
    return 'evening'


def random_hour():
    """Return random hour + AM/PM info (7am - 11pm)."""
    hr = random.choice(range(7, 23))
    ampm = 'am' if hr < 12 else 'pm'
    hr %= 12
    if hr == 0:
        hr = 12
    return hr, ampm


def deabstract(utt, dais):
    """De-abstract an utterance and a list of corresponding DAIs, so that
    a specific answer is provided.
    """
    # prepare some data to be used
    from_stop, to_stop = random.sample(STOPS, 2)
    time, ampm = random_hour()
    vehicle = random.choice(['subway', 'bus'])

    dais_out = []  # create a completely new structure, so that we keep the abstract original

    # process DAIs and deabstract them, along with the utterance
    for dai in dais:

        dai_out = DialogueActItem(dai.dat, dai.name, dai.value)
        dais_out.append(dai_out)

        if dai.name == 'from_stop':
            dai_out.value = from_stop
            utt_r = re.sub(r'(from |^)\*STOP', r'\1%s' % from_stop, utt)
        elif dai.name == 'to_stop':
            dai_out.value = to_stop
            utt_r = re.sub(r'(destination is|arrive (in|at)|to|towards?|for|into) \*STOP',
                           r'\1 %s' % to_stop, utt)
        elif dai.name == 'vehicle':
            dai_out.value = vehicle
            utt_r = re.sub(r'\*VEHICLE', vehicle, utt)
        elif 'time' in dai.name and dai.dat == 'inform':
            if re.search(r'\*TIME', utt):
                dai_out.value = 'now'
                utt_r = re.sub(r'\*TIME', 'now', utt)
            if re.search(r'\*NUMBER an hour', utt):
                dai_out.value = '0:30'
                utt_r = re.sub(r'\*NUMBER', 'half', utt)
            elif re.search(r'\*NUMBER minutes', utt):
                time, hr_val, num_word = random.choice(MINUTE_VALUES)
                dai_out.value = hr_val
                utt_r = re.sub(r'\*NUMBER', num_word, utt)
            elif re.search(r'\*NUMBER \*NUMBER', utt):
                dai_out.value = unicode(time) + ':30'
                utt_r = re.sub(r'\*NUMBER \*NUMBER', WORD_FOR_NUMBER[time] + ' thirty', utt)
            else:
                if 'time_rel' in dai.name:
                    time = random.randint(0, 4)
                dai_out.value = unicode(time) + ':00'
                utt_r = re.sub(r'\*NUMBER', WORD_FOR_NUMBER[time], utt)
        elif 'ampm' in dai.name:
            dai_out.value = ampm
            utt_r = re.sub(r'(in the) \*AMPM', r'\1 %s' % word_for_ampm(time, ampm), utt)
            utt_r = re.sub(r'\*AMPM', ampm, utt_r)
        elif dai.value is None or '*' not in dai.value or dai.dat != 'inform':
            continue  # some things do not need deabstracting
        else:
            raise NotImplementedError('Cannot deabstract slot: ' + dai.name + " -- " + utt)

        if utt_r == utt:
            raise NotImplementedError('Cannot replace slot: ' + dai.name + " -- " + utt + " / " + unicode(dais))

        utt = utt_r

    return utt, dais_out


def normalize_utterance(utt):
    """Normalize utterance (remove double streets, convert streets to stops)."""

    # TODO handle boroughs ??
    utt = re.sub(r'\*STREET and \*STREET', r'*STREET', utt)
    utt = re.sub(r'\*STREET', r'*STOP', utt)
    return utt


def normalize_da(da):
    """Normalize DA to contain only things that we would like to confirm or reply to."""

    # keep just request/inform/confirm, remove 2nd streets, remove boroughs
    dais = [dai for dai in da.dais
            if (dai.dat in ['request', 'inform', 'confirm'] and
                dai.name not in ['borough', 'to_street2', 'from_street2', 'task'])]

    # convert streets to stops
    for dai in dais:
        dai.name = re.sub('_street$', '_stop', dai.name)

    # default to departure time
    for dai in dais:
        dai.name = re.sub('^time', 'departure_time', dai.name)

    return dais


def generate_ack(ack_type, utt, dais):
    """Generate a confirmation/apology task for the given utterance and DAIs list."""

    ret = DataLine(dat=ack_type, abstr_utt=utt, abstr_da='&'.join([unicode(dai) for dai in dais]))

    utt, dais = deabstract(utt, [dai for dai in dais
                                 if re.match(ACK_SLOTS_REGEX, dai.name) and
                                 dai.dat in ['confirm', 'inform']])
    dais_str = ', '.join([dai.name + '=' + dai.value for dai in dais])
    if ack_type == 'apologize':
        dais_str = '*=notfound, ' + dais_str

    ret.utt = utt
    ret.da = dais_str
    return ret


def generate_reply(utt, dais):
    """Generate a reply task for the given utterance and DAIs list."""

    ret = DataLine(dat='reply', abstr_utt=utt, abstr_da='&'.join([unicode(dai) for dai in dais]))

    utt, dais = deabstract(utt, dais)

    # offer a ride (meeting the specifications in dais)
    if all([dai.dat in ['inform', 'confirm'] for dai in dais]):

        info = {dai.name: dai.value for dai in dais}
        if 'vehicle' not in info:
            info['vehicle'] = random.choice(['subway', 'bus'])
        if info['vehicle'] == 'subway':
            info['line'] = random.choice('1234567ABCDEFGJLMNQRZ')
        else:
            info['line'] = 'M' + str(random.choice(BUS_LINES))
        if 'ampm' not in info:
            if 'time' in info:
                time_val, _ = info['time'].split(':')
                time_val = int(time_val)
                if time_val < 7 or time_val == 12:
                    info['ampm'] = 'pm'
            if 'ampm' not in info:
                info['ampm'] = random.choice(['am', 'pm'])
        if 'departure_time' not in info:
            if 'time' in info:
                info['departure_time'] = info['time']
                del info['time']
            elif info['ampm'] == 'am':
                info['departure_time'] = str(random.choice(range(7, 12))) + ':00'
            else:
                info['departure_time'] = str(random.choice(range(1, 13))) + ':00'
        if 'from_stop' not in info:
            info['from_stop'] = random.choice(STOPS)
        if 'to_stop' not in info:
            remaining_stops = list(STOPS)
            remaining_stops.remove(info['from_stop'])
            info['to_stop'] = random.choice(remaining_stops)

        info['direction'] = info['to_stop']
        del info['to_stop']

        info['departure_time'] = re.sub(r'00$', '%02d' % random.choice(range(20)),
                                        info['departure_time'])
        info['departure_time'] += info['ampm']
        del info['ampm']

        for slot_name in ['departure_time_rel', 'time_rel',
                          'alternative', 'arrival_time', 'arrival_time_rel']:
            if slot_name in info:
                del info[slot_name]

        dais_str = [slot + '=' + value for slot, value in info.iteritems()]
        random.shuffle(dais_str)
        dais_str = ', '.join(dais_str)

    # offer additional information
    else:
        dais_str = ''
        if any([dai.name == 'distance' and dai.dat == 'request' for dai in dais]):
            dais_str += ', distance=%3.1f miles' % (random.random() * 12)
        if any([dai.name == 'num_transfers' and dai.dat == 'request' for dai in dais]):
            dais_str += ', num_transfers=%d' % random.choice(range(0, 3))
        if any([dai.name == 'duration' and dai.dat == 'request' for dai in dais]):
            dais_str += ', duration=%d minutes' % random.choice(range(10, 80))
        if any([dai.name == 'departure_time' and dai.dat == 'request' for dai in dais]):
            hr, ampm = random_hour()
            min = random.choice(range(60))
            dais_str += ', departure_time=%d:%02d%s' % (hr, min, ampm)
        if any([dai.name == 'arrival_time' and dai.dat == 'request' for dai in dais]):  # arrival_time_rel does not occur
            hr, ampm = random_hour()
            min = random.choice(range(60))
            dais_str += ', arrival_time=%d:%02d%s' % (hr, min, ampm)
        if dais_str == '':
            raise NotImplementedError('Cannot generate a reply for: ' + unicode(dais))

        dais_str = dais_str[2:]

    ret.utt = utt
    ret.da = dais_str
    return ret


def generate_request(utt, dais):
    """Generate a request -- ask about slots not present."""

    ret = DataLine(dat='request', abstr_utt=utt, abstr_da='&'.join([unicode(dai) for dai in dais]))
    slots = [dai.name for dai in dais if dai.dat in ['inform', 'confirm']]
    dais_str = ''

    if 'from_stop' not in slots:
        dais_str += ', from_stop=?'
    if 'to_stop' not in slots:
        dais_str += ', to_stop=?'

    dais_str = dais_str[2:]

    utt, _ = deabstract(utt, [dai for dai in dais if re.match(ACK_SLOTS_REGEX, dai.name)])

    ret.utt = utt
    ret.da = dais_str
    return ret


def combine_actions(act1, act2):

    ret = DataLine(dat='-'.join((act1.dat, act2.dat)),
                   abstr_utt=act1.abstr_utt,
                   abstr_da=act1.abstr_da,
                   utt=act1.utt,)

    ret.da = (act1.dat + ': ' + act1.da + '; ' + act2.dat + ': ' + act2.da)

    return ret


def process_utt(utt, da):
    """Process a single utterance + DA pair, generating corresponding tasks if applicable."""

    utt = normalize_utterance(utt)
    dais = normalize_da(da)

    ret = {}

    if not dais:  # skip things that did not contain anything to reply/confirm
        return ret

    # check if we should generate a confirmation task, and do it
    if any([dai.dat in ['inform', 'confirm'] and re.match(ACK_SLOTS_REGEX, dai.name)
            for dai in dais]):

        ret['confirm'] = generate_ack('confirm', utt, dais)

        if not any([dai.dat == 'request' for dai in dais]):
            ret['apologize'] = generate_ack('apologize', utt, dais)

            # check if we can generate a request for additional information
            slots = [dai.name for dai in dais if dai.dat in ['inform', 'confirm']]
            if not ('from_stop' in slots and 'to_stop' in slots) and 'alternative' not in slots:
                ret['request'] = generate_request(utt, dais)

    # generate a reply task
    ret['reply'] = generate_reply(utt, dais)

    # try combining confirm + reply/request in case the reply/request is short
    if 'confirm' in ret:
        if 'request' in ret and ret['request'].da.count(',') < 3:
            ret['confirm+request'] = combine_actions(ret['confirm'], ret['request'])
        if 'reply' in ret and ret['reply'].da.count(',') < 3:
            ret['confirm+reply'] = combine_actions(ret['confirm'], ret['reply'])

    return ret.values()


def main(args):

    data = []
    good_toks, good_types = 0, 0  # good contexts, useful for tasks
    fthr_toks, fthr_types = 0, 0  # filtered because of threshold
    fslt_toks, fslt_types = 0, 0  # filtered as they only contain slots
    frep_toks, frep_types = 0, 0  # filtered because no reply can be generated
    finished = {}

    with codecs.open(args.input_file, "r", 'UTF-8') as fh:
        for line in fh:
            print >> sys.stderr, 'Processing: ', line.strip()

            if line.count("\t") != 2:
                print >> sys.stderr, 'Invalid input format, skipping'
                continue

            occ_num, utt, da = line.strip().split('\t')
            da = DialogueAct(da_str=da)
            occ_num = int(occ_num)

            if occ_num < args.filter_threshold:
                print >> sys.stderr, 'Input "%s" has only %d occurrences, skipping' % (utt, occ_num)
                fthr_toks += occ_num
                fthr_types += 1
                continue

            if re.match(r'^(\*[A-Z_]+)(\s+\*[A-Z_]+)*$', utt):
                print >> sys.stderr, 'Input "%s" only contains slots, skipping' % utt
                fslt_toks += occ_num
                fslt_types += 1
                continue

            try:
                ret = process_utt(utt, da)
                if not ret:
                    frep_toks += occ_num
                    frep_types += 1
                else:
                    good_toks += occ_num
                    good_types += 1
                print >> sys.stderr, 'Result:', "\n".join(unicode(line) for line in ret)
                print >> sys.stderr, ''
                if args.occ_nums:
                    for ret_line in ret:
                        ret_line.occ_num = occ_num
                data.extend(ret)
            except NotImplementedError as e:
                frep_toks += occ_num
                frep_types += 1
                print >> sys.stderr, 'Error:', e

    if args.load_finished:
        with codecs.open(args.load_finished, "r", 'UTF-8') as fh:
            csvread = csv.reader(fh, delimiter=str(args.finished_csv_delim), quotechar=b'"')
            columns = DataLine.get_columns_from_header(csvread.next())
            for row in csvread:
                finished_line = DataLine.from_csv_line(row, columns)
                finished[finished_line.signature] = finished_line

    written = {}
    with codecs.getwriter('utf-8')(sys.stdout) as fh:
        # starting with the header
        csvwrite = csv.writer(fh, delimiter=b"\t", lineterminator="\n")
        csvwrite.writerow(DataLine.get_headers(args.occ_nums))
        for line in data:
            if line.signature in written:  # some lines may be duplicate, skip them
                print >> sys.stderr, 'Duplicate line:', line.signature
                continue
            # skip finished results (if they are loaded and if they should be skipped)
            if line.signature in finished:
                if finished[line.signature].slots != line.slots:
                    print >> sys.stderr, ('Slots changed for ', line.signature,
                                          '-- ignoring finished.')
                    csvwrite.writerow(line.as_tuple(args.occ_nums))
                elif not args.skip_finished:
                    finished[line.signature].occ_num = line.occ_num
                    csvwrite.writerow(finished[line.signature].as_tuple(args.occ_nums))
            # default case: not found among finished
            else:
                csvwrite.writerow(line.as_tuple(args.occ_nums))

            written[line.signature] = line

    print >> sys.stderr, ("\n\nGood: %d / %d\nThreshold: %d / %d\nSlots: %d / %d\nReply: %d / %d" %
                          (good_toks, good_types, fthr_toks, fthr_types, fslt_toks, fslt_types,
                           frep_toks, frep_types))

if __name__ == '__main__':
    ap = ArgumentParser()
    ap.add_argument('-f', '--filter-threshold', type=int, default=1)
    ap.add_argument('-l', '--load-finished', type=str, default='')
    ap.add_argument('-s', '--skip-finished', action='store_true')
    ap.add_argument('-d', '--finished-csv-delim', type=str, default="\t")
    ap.add_argument('-o', '--occ-nums', action='store_true')
    ap.add_argument('input_file')
    random.seed(0)
    args = ap.parse_args()
    main(args)
