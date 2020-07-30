import sys, getopt
from pathlib import Path
from os import mkdir
import re
#import pandas as pd
#import timing

#Dictionary that holds regex expressions
rx_tester_info = {}
rx_cal = {}
rx_cal_res = {}
rx_diag = {}

def load_tester_info(filepath):
    rev = ''
    dut = ''
    dut_sn = ''
    tester_model = ''
    self_test = ''
    with open(filepath) as f:
        line = f.readline()
        while line:
            key, match = parse_line(line, rx_tester_info)

            if key == 'rev':
                rev = match.group('rev').strip()
            elif key == 'dut':
                dut = match.group('dut').strip()
                if match.group('dut_sn'): dut_sn = match.group('dut_sn').strip()
                else: dut_sn = ''
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
    return dut_sn


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

                        board.history.append(Entry(res_match.group('date').strip(), res_match.group('time').strip(), mode, sn, rev, res, remark))
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
        for i in item.history:
            print(f'{i.date} | {i.time} | {i.mode} | {i.sn} | {i.rev}  | {i.res}   | {i.remark}')

    print(f'\nNumber of entries: {len(board_list)}')

def gen_csv_cal(board_list, tester_num, output):
    #Check if output directory exists, if not create it
    if not Path('./output').exists():
        try:
            mkdir('./output')
        except OSError:
            print('Failed creating output directory.')
            exit(2)

    with open(f'./output/{output}.csv', 'w') as f:
        f.write(f'Tester,Board,Slot,DUT SN,Date,Time,Mode,SN,REV,Result,Remark\n')
        for board in board_list:
            for i in board.history:
                f.write(f'{tester_num},{board.btype},{board.slot},\t{i.dut},\t{i.date},{i.time},{i.mode},\t{i.sn},{i.rev},{i.res},{i.remark}\n')
    
    print(f'Process finished. Output located at ./output/{output}.csv.')

def gen_csv_diag(entry_list, tester_num, output):
    #Check if output directory exists, if not create it
    if not Path('./output').exists():
        try:
            mkdir('./output')
        except OSError:
            print('Failed creating output directory.')
            exit(2)
    
    with open(f'./output/{output}.csv', 'w') as f:
        f.write(f'Tester,Board,Date,Time,Mode,SN,Result,Failure\n')
        for entry in entry_list:
            sn = entry.sn
            if not sn: sn = 'N/A' 
            f.write(f'{tester_num},{entry.name},\t{entry.date},{entry.time},Diag,\t{sn},{entry.res},{entry.err}\n')
    
    print(f'Process finished. Output located at ./output/{output}.csv.')
        
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
                dut = load_tester_info(log.path)
                load_cal_result(log.path, board_list)

                for item in board_list:
                    for entry in item.history:
                        entry.dut = dut

            print_cal_result(board_list)
            gen_csv_cal(board_list, tester_num, f'Summary_{tester_num}_Cal_{cal_files[0].date}_{cal_files[-1].date}')
        
        if len(diag_files):
            entry_list = []
            for log in diag_files:
                load_tester_info(log.path)
                entry_list += load_diag_result(log.path)

            #Print Diag Result on terminal
            print('-------------------------------------------------')
            for entry in entry_list:
                print(f'{entry.name} {entry.date} {entry.time} {entry.sn} {entry.res} {entry.err}')
            print(f'Number of entries: {len(entry_list)}')

            gen_csv_diag(entry_list, tester_num, f'Summary_{tester_num}_Diag_{diag_files[0].date}_{diag_files[-1].date}')
                
        
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
            dut = load_tester_info(filepath)
            load_cal_result(filepath, board_list)
            print_cal_result(board_list)

            for item in board_list:
                for entry in item.history:
                    entry.dut = dut

            gen_csv_cal(board_list, tester_num, f'Summary_{tester_num}_{log_mode}_{log_date}')

        #If DIAG mode    
        elif log_mode.lower() == 'diag' and len(tester_num) and len(log_date):
            entry_list = []

            load_tester_info(filepath)
            #board_list = preload_diag_result(filepath)
            entry_list = load_diag_result(filepath)

            #Print Diag Result on terminal
            print('-------------------------------------------------')
            for entry in entry_list:
                print(f'{entry.name} {entry.date} {entry.time} {entry.sn} {entry.res} {entry.err}')
            print(f'Number of entries: {len(entry_list)}')

            gen_csv_diag(entry_list, tester_num, f'Summary_{tester_num}_{log_mode}_{log_date}')
        else:
            print(f'Invalid log file. {filename}')
            exit(2)
        
    #load_cal_result('log.log')
    #load_diag_result('log.log')

def load_diag_result(filepath):
    master_entry_list = []
    sn_board_list = [] #entries from individual lines
    table_left = [] #entries from table - left
    table_right = [] #entries from table - right
    table_list = [] #table left + right
    with open(filepath) as f:
        line = f.readline()

        while line:
            key, match = parse_line(line, rx_diag)

            if key == 'testing':
                sn = match.group('sn').strip()
                btype = match.group('btype').strip()
                error = ''

                #Read next line to check for errors
                line = f.readline() 
                while line:
                    key2, match2 = parse_line(line, rx_diag)
                    
                    #error found
                    if key2 == 'error':
                        err_code = match2.group('error').strip()

                        #if no listed errors yet
                        if not len(error):
                            error += f'{err_code}'
                        else:
                            if not error.split('_')[-1] == err_code:
                                error += f'_{err_code}'
                    else:
                        #Time to save what we currently have
                        if len(error) : res = 'PASS'
                        else: res = 'FAIL'
                        entry = Entry('', '', 'diag', sn, '', res, '')
                        entry.err = error
                        entry.name = btype
                        sn_board_list.append(entry)
                        break

                    line = f.readline()

            elif key == 'diag_table_long':
                slot1 = match.group('slot')
                if not slot1: slot1 = ''
                name1 = match.group('btype').strip() + ' ' + slot1
                res1 = match.group('res').strip() 
                entry1 = Entry('', '', 'diag', '', '', res1, '')
                entry1.name = name1
                if res1 != 'N/A' and len(res1):
                    table_left.append(entry1)

                slot2 = match.group('slot2')
                if not slot2: slot2 = ''
                name2 = match.group('btype2').strip() + ' ' + slot2
                res2 = match.group('res2').strip()
                entry2 = Entry('', '', 'diag', '', '', res2, '')
                entry2.name = name2
                if res2 != 'N/A' and len(res2):
                    table_right.append(entry2)

                line = f.readline()
                continue

            elif key == 'diag_table_end':
                table_list = table_left + table_right
                
                for sn_entry in sn_board_list:
                    for table_entry in table_list:
                        if sn_entry.name in table_entry.name and not table_entry.sn:
                            table_entry.sn = sn_entry.sn
                            table_entry.err = sn_entry.err
                            break
                
                for entry in table_list:
                    entry.date = match.group('date').strip()
                    entry.time = match.group('time').strip()

                    #print(f'{entry.name} {entry.date} {entry.time} {entry.sn} {entry.res} {entry.err}')
                
                master_entry_list += table_list
                #reset
                sn_board_list = [] #entries from individual lines
                table_left = [] #entries from table - left
                table_right = [] #entries from table - right
                table_list = [] #table left + right


                line = f.readline()
                continue
           
            else:
                line = f.readline()     
                
    return master_entry_list

def preload_diag_result(filepath):
    """
    Preloads the board with information from log table summary.

    Parameters:
    board_list -- list containing boards to preload
    """
    finished = False

    board_list = []
    table_left = []
    table_right = []

    with open(filepath) as f:
        line = f.readline()
        while line:
            #print(line)
            #Parse every line using parse_line and store it to key and match
            key, match = parse_line(line, rx_diag)

            if key == 'diag_table_long':
                slot1 = match.group('slot')
                if not slot1:
                    slot1 = 'N/A'
                board1 = Board(match.group('btype').strip(), 'N/A', slot1)
                board1.test = match.group('test').strip()
                table_left.append(board1)

                slot2 = match.group('slot2')
                if not slot2:
                    slot2 = 'N/A'
                board2 = Board(match.group('btype2').strip(), 'N/A', slot2)
                board2.test = match.group('test2').strip()
                table_right.append(board2)
            elif key == 'diag_table_end':
                finished = True
            
            if finished: break
            else: line = f.readline()
    
    board_list = table_left + table_right

    """ for item in board_list:
        print(f'{item.test} {item.btype} {item.slot}')
        
    print(f'Number of entries: {len(board_list)}') """

    return board_list

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

def parse_line(line, dict):
    #For each entry in the regex dictionary, check if it has a match with the input line
    for key, rx in dict.items():
        match = rx.search(line)
        if match:
            #If it matches, return key and match object
            return key, match
    
    #Else, return None
    return None, None
        
def usage():
    print('single mode: test.py --file <inputfile>')
    print('directory mode: test.py --dir <inputfile> -c or -d or -cd')

class Board:
    """
    A class to represent a tester board.

    Attributes:
    btype -- board type
    sn -- serial number
    slot -- slot number
    rev -- revision number

    cal_date -- last calibration date
    history -- list of class Entry documenting test results

    """
    def __init__(self, btype, sn, slot):
        """
        Constructor method for Board.

        Parameters:
        btype -- board type
        sn -- serial number
        slot -- slot number
        """
        #default values, listed here for convenience
        self.btype = btype
        self.sn = sn
        self.slot = slot
        self.rev = -1 

        #Only for cal logs
        self.cal_date = '' 
        self.history = []

        #Only for diag logs
        self.test = ''

class Entry:
    """
    A class to represent a test result entry.

    Attributes:
    date -- date of entry
    time -- time of entry
    mode -- test mode for entry (cal, chk, diag)
    sn -- serial number
    rev -- revision number
    res -- result (PASS/FAIL/etc)
    remark -- added information for the entry, shows failure details for diag mode
    err -- error codes

    """
    def __init__(self, date, time, mode, sn, rev, result, remark):
        """
        Constructor method for Entry.

        Parameters:
        date -- date of entry
        time -- time of entry
        mode -- test mode for entry (cal, chk, diag)
        sn -- serial number
        rev -- revision number
        res -- result (PASS/FAIL/etc)
        remark -- added information for the entry, shows failure details for diag mode
        dut -- DUT board information (SN for Cal, Model for Diag)
        """
        self.date = date
        self.time = time
        self.mode = mode
        self.sn = sn
        self.rev = rev
        self.res = result
        self.remark = remark
        self.dut = ''

        #For diag only
        self.err = ''
        self.name = ''

class Log():
    """
    A class to represent a log file.

    Attributes:
    tester_num -- tester number of log file
    path -- path location of log file
    date -- date of log file
    """
    def __init__(self, tester_num, path, date):
        """
        Constructor method for Log.

        Parameters:
        tester_num -- tester number of log file
        path -- path location of log file
        date -- date of log file
        """
        self.tester_num = tester_num
        self.path = path
        self.date = date

if __name__ == '__main__':
    main(sys.argv[1:])