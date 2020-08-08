from pathlib import Path
from os import mkdir
from dataclasses import dataclass
from shutil import rmtree
import jsonpickle
import json
import re
import timing
import argparse
import os

rx_diag = {}
rx_cal = {}
rx_cal_res = {}

jsonpickle.set_encoder_options('json', indent=2)

parser = argparse.ArgumentParser()
parser.add_argument('-s','--setup', action='store_true', help='Clear existing board profiles and generate new ones.')
parser.add_argument('-d','--dir', help='Directory path to monitor for new logs.', required=True)

def main():
    args = parser.parse_args()

    ''' Constants ----------------------- '''
    global rx_tester_info
    global rx_cal
    global rx_cal_res
    global rx_diag

    rx_tester_info = load_regex_dict('config/rx_tester_info.csv')
    rx_cal = load_regex_dict('config/rx_cal.csv')
    rx_cal_res = load_regex_dict('config/rx_cal_res.csv')
    rx_diag = load_regex_dict('config/rx_diag.csv')

    ''' Monitoring Start ----------------------- '''
    filepath = args.dir
    #filepath = 'C:/Users/a0489136/Desktop/Project/Main Project/samplelogs/clprea83/Cal_files'
    #filepath = 'C:/Users/a0489136/Desktop/test/samplelogs/logs_Ea90'

    #Clear and Generate profiles
    if args.setup:
        clear_filelist()
        
        #Get list of logs to process
        queue = get_jobs(filepath)
        #print(f'Found {len(queue)} logs to record.')
        tester_name = str(queue[0]).replace('/','\\').split('\\')
        tester_name = tester_name[-1].split('_')[1]

        #Clear old profiles and generate new ones
        Board.clear_all_profiles()
        gen_profiles('./config/setup.log', tester_name)

    else:
        #Get list of logs to process
        queue = get_jobs(filepath)
        print(f'Found {len(queue)} new logs to record in {filepath}.')

        #Load profiles from ./profiles
        board_list = load_profiles()

        #Process each job in queue
        cal_count = 0
        diag_count = 0
        cal_entry_count = 0
        diag_entry_count = 0
        if queue: print('\nReading new logs..')
        for job in queue:
            filename = str(job).replace('/','\\').split('\\')
            filename = filename[-1]
            print(filename)
            log_mode = filename.split('_')[0]

            if log_mode.lower() == 'cal':
                cal_entry_count += load_cal_result(job, board_list, filename)
                cal_count += 1
            elif log_mode.lower() == 'diag':
                diag_entry_count += load_diag_result(job, board_list, filename)
                diag_count += 1

        if cal_count > 0: print(f'Total calibration logs processed: {cal_count}')
        if diag_count > 0: print(f'Total diagnostic logs processed: {diag_count}')

        #Save profile changes to disk
        save_profiles(board_list)

        #Add finished jobs to file_list.json
        update_filelist(queue)

def load_diag_result(filepath, board_list, filename):
    '''
    Reads diagnostic log located in filepath and adds entries to diag_history of boards in board_list
    '''
    master_entry_list = []
    sn_board_list = [] #entries from individual lines
    table_left = [] #entries from table - left
    table_right = [] #entries from table - right
    table_list = [] #table left + right
    with open(filepath) as f:
        line = f.readline()
        dut = ''
        while line:
            key, match = parse_line(line, rx_diag)

            if key == 'dut':
                dut = match.group('dut').strip()
                line = f.readline()
                continue
            elif key == 'testing':
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
                        if not dut: dut = 'N/A'
                        entry = DiagEntry(dut, '', '', sn, res, error, filename, btype, sn)
                        sn_board_list.append(entry)
                        break

                    line = f.readline()

            elif key == 'diag_table_setup':
                #Match left side of table
                slot1 = match.group('slot')
                if not slot1: slot1 = '00'
                name1 = match.group('btype').strip()
                res1 = match.group('res').strip() 
                entry1 = DiagEntry(dut, '', '', 'N/A', res1, '', filename, name1, slot1)
                if res1 != 'N/A' and len(res1):
                    table_left.append(entry1)

                #Match right side of table
                slot2 = match.group('slot2')
                if not slot2: slot2 = '00'
                name2 = match.group('btype2').strip()
                res2 = match.group('res2').strip()
                entry2 = DiagEntry(dut, '', '', 'N/A', res2, '', filename, name2, slot2)
                if res2 != 'N/A' and len(res2):
                    table_right.append(entry2)

                line = f.readline()
                continue

            elif key == 'diag_table_end':
                table_list = table_left + table_right
                
                for sn_entry in sn_board_list:
                    for table_entry in table_list:
                        if sn_entry.tname in table_entry.tname and table_entry.sn == 'N/A':
                            table_entry.sn = sn_entry.sn
                            table_entry.remark = sn_entry.remark
                            break
                        if sn_entry.tname == 'MCU' and table_entry.tname == 'Master Clock':
                            table_entry.sn = sn_entry.sn
                            table_entry.remark = sn_entry.remark
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
    count = 0
    for entry in master_entry_list:
        for board in board_list:
            """ if entry.tname == 'Master Clock' and board.name == 'Master Clock':
                print('hi') """
            if entry.tname.lower() in board.name.lower() and board.slot in entry.tslot:
                if entry.sn == '': sn = 'N/A'
                board.diag_history.append(entry)
                #entry.bool = True
                #master_entry_list.remove(entry)
                count += 1
                break
    
    """ for entry in master_entry_list:
        if not entry.bool:
            print(f'{entry.tname} {entry.tslot} {entry.date} {filepath}') """

    
    #print(f'number of saved entries: {count}')

    #print(f'Processed diagnostic log from {filepath}.')

    return count

def load_cal_result(filepath, board_list, filename):
    '''
    Reads calibration log located in filepath and adds entries to cal_history of boards in board_list
    '''
    count = 0
    with open(filepath) as f:
        line = f.readline()
        #loaded_tester_info = False
        dut = ''
        dut_pn = ''
        self_test = ''
        backup_date = ''
        backup_time = ''
        last_line = None
        while line:
            #print(line)
            #Parse every line using parse_line and store it to key and match
            """ if loaded_tester_info:
                key, match = parse_line(line, rx_cal)
            else:
                key, match = parse_line(line, rx_tester_info) """
            
            key, match = parse_line(line, rx_cal)

            #If key is not empty, it means we got a match
            if key == 'self_test':
                self_test = match.group('self_test')

            elif key == 'dut':
                dut = match.group('dut_sn')
                dut_pn = match.group('dut')
            
            #Backup date and time is in case it fails Self-test
            elif key == 'backup_date':
                backup_date = match.group('date').strip()
                backup_time = match.group('time').strip()

            elif key not in ('dut', 'self_test') and key:
                btype = match.group('btype').strip() #Board name
                slot = match.group('slot').strip() #Stores board slot

                mode = match.group('mode').strip() #Stores current test mode (Cal or Chk)
                sn = match.group('sn').strip() #Stores board SN
                rev = match.group('rev').strip()
                remark = ''

                #Some boards do not include slot number in the beginning (MCU and DIG INTEG)
                #For now, set it to -1
                if not(len(slot)):
                    slot = '00'
                
                #Get the correct board reference
                board = None #current board reference
                for item in board_list:
                    if item.name.lower() == btype.lower() and item.slot == slot:
                        board = item
                        break
                    
                    if item.name == 'Master Clock' and btype == 'MCU':
                        board = item
                        break
                    
                    if item.slot.isnumeric():
                        if item.name.lower() == btype.lower() and int(item.slot) == int(slot):
                            board = item
                            break

                #Check for results
                res_line = f.readline()
                while(res_line):
                    res_key, res_match = parse_line(res_line, rx_cal_res)

                    if res_key == 'cal' or  res_key == 'chk':
                        #Change UPDATED to PASS
                        if res_match.group('res').strip() == 'UPDATED': res = 'PASS'
                        else: res = res_match.group('res').strip()

                        date = res_match.group('date').strip()
                        time = res_match.group('time').strip()
                        if self_test == '': self_test = 'N/A'
                        board.cal_history.append(CalEntry(dut, date, time, sn, res, remark, filename, mode, rev, self_test, dut_pn))
                        count += 1
                        break
                    
                    elif res_key == 'self_test':
                        board.cal_history.append(CalEntry(dut, backup_date, backup_time, sn, 'FAIL', '', filename, mode, rev, self_test, dut_pn))
                        count += 1
                        f.seek(last_line)
                        break

                    """ elif res_key == 'fail':
                        board.cal_history.append(CalEntry(dut, backup_date, backup_time, sn, 'FAIL', '', filename, mode, rev, self_test, dut_pn))
                        count += 1
                        break """
                    
                    
                    last_line = f.tell()
                    res_line = f.readline()

            #Go to next line
            line = f.readline()
    #print(f'{count} entries done')
    #print(f'Processed calibration log from {filepath}.')

    return count

def gen_profiles(filepath, tester):
    '''
    Generates board profiles from a log file. Only has to be used once unless there are physical changes to the tester.
    
    Returns a list of Board objects.
    '''

    finished = False
    table_left = []
    table_right = []
    setup_dict = {'diag_table_setup': rx_diag['diag_table_setup'], 'diag_table_end': rx_diag['diag_table_end']}

    with open(filepath) as f:
        line = f.readline()
        while line:
            #print(line)
            #Parse every line using parse_line and store it to key and match
            key, match = parse_line(line, setup_dict)

            if key == 'diag_table_setup':
                slot1 = match.group('slot')
                if not slot1:
                    slot1 = '00'
                board1 = Board(match.group('btype').strip(), slot1, tester)
                table_left.append(board1)

                slot2 = match.group('slot2')
                if not slot2:
                    slot2 = '00'
                board2 = Board(match.group('btype2').strip(), slot2, tester)
                table_right.append(board2)
            elif key == 'diag_table_end':
                finished = True
            
            if finished: break
            else: line = f.readline()

    board_list = table_left + table_right

    for item in board_list:
        if item.name == 'DPU':
            item.name = 'DPU16'
        item.generate_profile()

    print(f'Generated {len(table_left + table_right)} new board profiles.')

    return table_left + table_right

def load_profiles():
    '''
    Loads existing profiles in ./profiles and returns them as a list of Board objects
    '''
    board_list = []
    for profile in Path('./profiles').iterdir():
        if profile.is_file():
            #load profile
            with open(profile, 'r') as f:
                json_str = f.read()
                board = jsonpickle.decode(json_str)
                #print(f'{board.name} {board.slot} {board.tester}')
                board_list.append(board)
    
    print(f'{len(board_list)} board profiles loaded.')

    return board_list

def save_profiles(board_list):
    '''
    Save profiles from board_list to JSON format located in ./profile.
    '''
    for board in board_list:
        board.generate_profile()

def get_jobs(filepath):
    '''
    Returns a list of log file paths (STR) to be processed next.
    '''
    files_actual = []
    files_json = []
    process_queue = []

    for child in Path(filepath).iterdir():
        if child.is_file():
            files_actual.append(str(child))

    #check if file_list.json exists
    if Path(f'./config/file_list.json').exists():
        #read json file
        with open('./config/file_list.json', 'r') as f:
            try:
                files_json = json.load(f)
            except json.decoder.JSONDecodeError:
                print('Reading file_list: The file_list.json is either empty or corrupted. Continuing..')
        
        for item in files_actual:
            if item not in files_json and item.lower().endswith('.log'):
                process_queue.append(item)
    else:
        process_queue = files_actual.copy()
    
    return process_queue

def update_filelist(done_jobs):
    '''
    Updates ./config/file_list.json to add processed logs
    '''
    #save to json
    files_json = []
    
    if Path(f'./config/file_list.json').exists(): mode = 'r+'
    else: mode = 'w'
    #read json file
    with open('./config/file_list.json', mode) as f:
        try:
            if mode == 'r+': files_json = json.load(f)
        except json.decoder.JSONDecodeError:
            print('Saving file_list: The file_list.json is either empty or corrupted. Continuing..')
        finally:
            for item in done_jobs:
                if item not in files_json and item.lower().endswith('.log'):
                    files_json.append(item)
            f.seek(0)
            json.dump(files_json, f, indent=4)

def clear_filelist():
    if Path(f'./config/file_list.json').exists():
        os.remove(f'./config/file_list.json')

def parse_line(line, dict):
    '''
    Matches RegEx from dict to line string and returns the key and match.
    '''
    #For each entry in the regex dictionary, check if it has a match with the input line
    for key, rx in dict.items():
        match = rx.search(line)
        if match:
            #If it matches, return key and match object
            return key, match
    
    #Else, return None
    return None, None

def load_regex_dict(filepath):
    '''
    Returns a dictionary loaded with RegEx from filepath.
    '''
    dict = {}
    with open(filepath) as f:
        line = f.readline()
        while line:
            #Parse line and split into key and value then store into dictionary
            x = line.strip().strip('\n').split(',',1)
            dict[x[0]] = re.compile(x[1])
            line = f.readline()
    return dict

class Board(object):
    '''
    Class representing tester board objects.
    '''
    def __init__(self, name, slot, tester):
        '''
        Constructor for Board.

        Arguments:
        name -- board name
        slot -- board slot
        tester -- tester name
        '''
        self.name = name
        self.slot = slot
        self.tester = tester
        self.path = None

        self.cal_history = []
        self.diag_history = []
        
    def generate_profile(self):
        '''
        Converts Board instance to json format and outputs it in ./profile.
        '''
        if not Path('./profiles').exists():
            try:
                mkdir('./profiles')
            except OSError:
                print('Failed creating profile directory.')
        slot = self.slot.replace('>', '', 1)
        if not self.path: self.path = f'./profiles/{self.name}_{slot}.json'
        with open(self.path, 'w') as f:
            board_json = jsonpickle.encode(self)
            f.write(board_json)
    
    def add_cal_entry(self, entry):
        '''
        Adds an entry to cal_history of this Board instance.
        '''
        self.cal_history.append(entry)

    def add_diag_entry(self, entry):
        '''
        Adds an entry to diag_history of this Board instance.
        '''
        self.diag_history.append(entry)
    
    def clear_cal_history(self):
        '''
        Clears the cal_history of this Board instance.
        '''
        self.cal_history.clear()

    def clear_diag_history(self):
        '''
        Clears the diag_history of this Board instance.
        '''
        self.diag_history.clear()
    
    @classmethod
    def clear_all_profiles(cls):
        '''
        Clears all board profiles located in ./profile.
        '''
        if Path('./profiles').exists():
            try:
                rmtree('./profiles')
            except OSError:
                print('Failed deleting profile directory.')
        
        print('Directory ./profiles has been deleted. All board profiles are cleared.')
           
class EntryBase(object):
    '''
    Base class for log entries.
    '''
    def __init__(self, dut, date, time, sn, result, remark, logname):
        self.dut = dut
        self.date = date
        self.time = time
        self.sn = sn
        self.result = result
        self.remark = remark
        self.logname = logname

class CalEntry(EntryBase):
    '''
    Class for calibration log entries. Inherits from EntryBase.
    '''
    def __init__(self, dut, date, time, sn, result, remark, logname, mode, rev, self_test, dut_pn):
        EntryBase.__init__(self, dut, date, time, sn, result, remark, logname)
        self.mode = mode
        self.rev = rev
        self.self_test = self_test
        self.dut_pn = dut_pn

class DiagEntry(EntryBase):
    '''
    Class for diagnostic log entries. Inherits from EntryBase.
    '''
    def __init__(self, dut, date, time, sn, result, remark, logname, tname, tslot):
        EntryBase.__init__(self, dut, date, time, sn, result, remark, logname)
        self.tname = tname
        self.tslot = tslot
        #self.bool = False

if __name__ == '__main__':
    main()