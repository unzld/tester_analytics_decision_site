import sys, getopt
from pathlib import Path
import re
#import pandas as pd
#import timing

#Dictionary that holds regex expressions
rx_tester_info = {}
rx_cal = {}
rx_cal_res = {}
rx_diag = {}

def parse_line(line, dict):
    #For each entry in the regex dictionary, check if it has a match with the input line
    for key, rx in dict.items():
        match = rx.search(line)
        if match:
            #If it matches, return key and match object
            return key, match
    
    #Else, return None
    return None, None

def load_tester_info(filepath):
    with open(filepath) as f:
        line = f.readline()
        rev = ''
        dut = ''
        dut_sn = ''
        tester_model = ''
        self_test = ''

        while line:
            key, match = parse_line(line, rx_tester_info)

            if key == 'rev':
                rev = match.group('rev').strip()
            elif key == 'dut':
                dut = match.group('dut').strip()
                dut_sn = match.group('dut_sn').strip()
            elif key == 'tester_model':
                tester_model = match.group('tester_model').strip()
            elif key == 'self_test':
                self_test = match.group('self_test').strip()

            if len(rev) and len(dut) and len(tester_model):
                break
            else:
                line = f.readline()

        print('-------------------------------------------------')
        print(f'Tester Platform: {tester_model}')
        print(f'DUT Board: {dut} Serial #: {dut_sn}')
        print(f'Revision Version: {rev}')
        if self_test:
            print(f'Self Test: {self_test}')


def load_cal_result(filepath, board_list):
    with open(filepath) as f:
        line = f.readline()
        while line:
            #print(line)
            #Parse every line using parse_line and store it to key and match
            key, match = parse_line(line, rx_cal)

            #If key is not empty, it means we got a match
            if key:
                mode = match.group('mode').strip() #Stores current test mode (Cal or Chk)
                btype = match.group('btype').strip()
                sn = match.group('sn').strip() #Stores board SN
                slot = match.group('slot').strip() #Stores board slot
                rev = match.group('rev').strip()
                remark = ''

                #Some boards do not include slot number in the beginning (MCU and DIG INTEG)
                #For now, set it to -1
                if not(len(slot)):
                    slot = -1
                
                #Format slot as number
                slot = str(int(slot))
                
                #Create new instance of Board class and fill it up with info we only have (type, sn, slot)
                board = Board(btype, sn, slot)
                board.rev = rev

                exists = False
                #If board list is not empty, check if the current board is listed already
                if len(board_list):
                    for item in board_list:
                       #If it does exist already, set 'board' to that board from the list
                        if item.btype == btype and item.slot == slot:
                            #Detect physical board changes
                            if item.sn != sn:
                                remark = f'Changed board from SN #{item.sn} to SN #{sn}'
                                item.sn = sn
                                item.rev = rev
                            exists = True
                            board = item

                #Append new board to board list if it doesn't exist yet
                if not(exists):
                    board_list.append(board)

                #Check for results
                res_line = f.readline()
                while(res_line):
                    res_key, res_match = parse_line(res_line, rx_cal_res)

                    if res_key == 'cal_date':
                        #Record date
                        board.cal_date = res_match.group('cal_date').strip()
                    elif res_key == 'cal' or  res_key == 'chk':
                        #Change UPDATED to PASS
                        if res_match.group('res').strip() == 'UPDATED': res = 'PASS'
                        else: res = res_match.group('res').strip()

                        board.cal_history.append(Entry(res_match.group('date').strip(), res_match.group('time').strip(), mode, sn, rev, res, remark))
                        break
                    
                    res_line = f.readline()
                    
            #Go to next line
            line = f.readline()

def print_cal_result(board_list):
    for item in board_list:
        print('-------------------------------------------------')
        print(f'Board: {item.btype} | SN: {item.sn} | REV: {item.rev} | Slot: {item.slot}')
        print(f'Last Calibration Date: {item.cal_date}')

        print('\nCalibration History')
        print('Date     | Time     | Mode | SN    | REV | Result | Remarks')
        for i in item.cal_history:
            print(f'{i.date} | {i.time} | {i.mode} | {i.sn} | {i.rev}  | {i.res}   | {i.remark}')

    print(f'\nNumber of entries: {len(board_list)}')

def gen_csv_cal(board_list, tester_num, output):
    with open(f'{output}.csv', 'w') as f:
        f.write(f'Tester,Board,Slot,Date,Time,Mode,SN,REV,Result,Remark\n')
        for board in board_list:
            for i in board.cal_history:
                f.write(f'{tester_num},{board.btype},{board.slot},\t{i.date},{i.time},{i.mode},\t{i.sn},{i.rev},{i.res},{i.remark}\n')


def load_diag_result(filepath):
    #List that stores board information
    test_list = []
    board_list = []
    with open(filepath) as f:
        line = f.readline()
        start_list = []
        end_list = []
        date_list = []
        lineno = 1
        while(line):
            key, match = parse_line(line, rx_diag)
            if key == 'diag_table_start':
                start_list.append(lineno)
            elif key == 'diag_table_end':
                end_list.append(lineno)
                date_list.append(match.group('date').strip())

            lineno += 1
            line = f.readline()
        
        if len(start_list) != len(end_list) != len(date_list):
            print('Invalid log file.') #something is wrong, log file is corrupted/tampered
        else:
            #Store test runs in a list
            for i in start_list:
                idx = start_list.index(i)
                test_list.append(Test(start_list[idx], end_list[idx], date_list[idx]))
        
        for item in test_list:
            print(f'{item.start_idx} {item.end_idx} {item.date}')


def load_regex_dict(filepath):
    dict = {}
    with open(filepath) as f:
        line = f.readline()
        while line:
            #Parse line and split into key and value then store into dictionary
            x = line.strip().strip('\n').split(',',1)
            dict[x[0]] = re.compile(x[1])
            line = f.readline()
    return dict

def main(argv):
    #START ---- Capture valid and invalid parameters ----
    try:
        opts, args = getopt.getopt(argv,"cd", ["file=", "dir="])
    except getopt.GetoptError as err:
        print(err)
        usage()
        sys.exit(2)
    
    #Set defaults
    mode = ''
    filepath = ''
    cal = False
    diag = False

    for o, a in opts:
        if o == '--file' or o == '--dir':
            if not(mode):
                mode = o
                filepath = a
            else:
                print('invalid usage: use either single or directory mode')
                usage()
                sys.exit(2)
        elif o == '-c':
            cal = True
        elif o == '-d':
            diag = True
    
    if len(argv) > 4 or len(argv) < 2:
        usage()
        exit(2)
    if mode == '--file' and (cal or diag):
        print('invalid usage: use either single or directory mode')
        usage()
        sys.exit(2)
    if mode == '--dir' and (not(cal) and not(diag)):
        print('invalid usage: use either single or directory mode')
        sys.exit(2)
    
    #END ---- Capture valid and invalid parameters ----

    #Load regex config files
    #Note to self: might be better to not use global variables here
    global rx_tester_info
    global rx_cal
    global rx_cal_res
    global rx_diag

    rx_tester_info = load_regex_dict('config/rx_tester_info.csv')
    rx_cal = load_regex_dict('config/rx_cal.csv')
    rx_cal_res = load_regex_dict('config/rx_cal_res.csv')
    rx_diag = load_regex_dict('config/rx_diag.csv')

    #List that stores all board objects
    board_list = []

    #Handle directory mode
    if mode == '--dir':
        cal_files = []
        diag_files = []
        tester_num = ''

        if cal:
            cal_files, tester_num = get_logs(filepath, 'cal')
        if diag:
            diag_files, tester_num = get_logs(filepath, 'diag')

        if cal: print(f'Number of Calibration Logs: {len(cal_files)}')
        if diag: print(f'Number of Diagnostic Logs: {len(diag_files)}')

        if len(cal_files):
            for log in cal_files:
                load_tester_info(log.path)
                load_cal_result(log.path, board_list)

            print_cal_result(board_list)
            gen_csv_cal(board_list, tester_num, f'Summary_{tester_num}_Cal_{cal_files[0].date}_{cal_files[-1].date}')
        
    #Handle single file mode    
    elif mode == '--file':
        #Get filename
        filename = str(filepath).replace('/','\\').split('\\')
        filename = filename[-1]

        log_mode = filename.split('_')[0]
        tester_num = ''
        log_date = ''
        
        #If file has a valid file
        if log_mode.lower() in ('cal', 'diag') and len(filename.split('_')) > 2:
            #Set log information
            tester_num = filename.split('_')[1]
            log_date = filename.split('_')[2].split('.')[0]

        #If CAL mode
        if log_mode.lower() == 'cal' and len(tester_num) and len(log_date):
            load_tester_info(filepath)
            load_cal_result(filepath, board_list)
            print_cal_result(board_list)
            gen_csv_cal(board_list, tester_num, f'Summary_{tester_num}_{log_mode}_{log_date}')
        else:
            print(f'Invalid log file. {filename}')
            exit(2)
        
    #load_cal_result('log.log')
    #load_diag_result('log.log')

#Populate filelists depending on mode: cal or diag or both
def get_logs(filepath, mode):
    file_list = []
    tester_num = ''
    for child in Path(f'{filepath}').iterdir():
        #Parse file name for tester and log information
        filename = str(child).replace('/','\\').split('\\')
        filename = filename[-1]
        
        log_mode = filename.split('_')[0]
        log_date = ''
        
        #If file has a valid file
        if log_mode.lower() in ('cal', 'diag') and len(filename.split('_')) > 2:
            tester_num = filename.split('_')[1]
            log_date = filename.split('_')[2].split('.')[0]

        if log_mode.lower() == mode and len(tester_num) and len(log_date):
            file_list.append(Log(tester_num, child, log_date))

    return file_list, tester_num
        
def usage():
    print('single mode: test.py --file <inputfile>')
    print('directory mode: test.py --dir <inputfile> -c or -d or -cd')

class Board:
    def __init__(self, btype, sn, slot):
        #default values, listed here for convenience
        self.btype = btype
        self.sn = sn
        self.slot = slot
        self.rev = -1 

        #Only for cal logs
        self.cal_date = '' 
        self.cal_history = []
        self.chk_history = []

#Class definition for cal/check/diag entries
class Entry:
    def __init__(self, date, time, mode, sn, rev, result, remark):
        self.date = date
        self.time = time
        self.mode = mode
        self.sn = sn
        self.rev = rev
        self.res = result
        self.remark = remark

#Class definition for diag test entries
class Test:
    def __init__(self, start_idx, end_idx, date):
        self.start_idx = start_idx
        self.end_idx = end_idx
        self.date = date

#Class definition for log files
class Log():
    def __init__(self, tester_num, path, date):
        self.tester_num = tester_num
        self.path = path
        self.date = date

if __name__ == '__main__':
    main(sys.argv[1:])